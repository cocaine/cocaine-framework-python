#
#    Copyright (c) 2012+ Anton Tyurin <noxiouz@yandex.ru>
#    Copyright (c) 2011-2014 Other contributors as noted in the AUTHORS file.
#
#    This file is part of Cocaine.
#
#    Cocaine is free software; you can redistribute it and/or modify
#    it under the terms of the GNU Lesser General Public License as published by
#    the Free Software Foundation; either version 3 of the License, or
#    (at your option) any later version.
#
#    Cocaine is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#    GNU Lesser General Public License for more details.
#
#    You should have received a copy of the GNU Lesser General Public License
#    along with this program. If not, see <http://www.gnu.org/licenses/>.
#

import functools
import itertools
import socket
import time
import warnings
import weakref

import six

from tornado.gen import Return
from tornado.ioloop import IOLoop
from tornado.locks import Lock
from tornado.tcpclient import TCPClient

from .channel import Channel
from .channel import Rx
from .channel import Tx
from .channel import manage_headers
from .headers import CocaineHeaders
from .log import servicelog
from .trace import get_trace_adapter, update_dict_with_trace
from .util import generate_service_id, msgpack_packb, msgpack_unpacker
from ..decorators import coroutine
from ..exceptions import DisconnectionError, ServiceConnectionError


def weak_wrapper(weak_service, method_name, *args, **kwargs):
    service = weak_service()
    if service is None:
        return

    return getattr(service, method_name)(*args, **kwargs)


def set_keep_alive(sock, idle=10, interval=5, fails=5):
    """Sets the keep-alive setting for the peer socket.

    :param sock: Socket to be configured.
    :param idle: Interval in seconds after which for an idle connection a keep-alive probes
      is start being sent.
    :param interval: Interval in seconds between probes.
    :param fails: Maximum number of failed probes.
    """
    import sys

    sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
    if sys.platform in ('linux', 'linux2'):
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, idle)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, interval)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, fails)
    elif sys.platform == 'darwin':
        sock.setsockopt(socket.IPPROTO_TCP, 0x10, interval)
    else:
        # Do nothing precise for unsupported platforms.
        pass


class BaseService(object):
    def __init__(self, name, endpoints, io_loop=None):
        if io_loop:
            warnings.warn('io_loop argument is deprecated.', DeprecationWarning)
        # If it's not the main thread
        # and a current IOloop doesn't exist here,
        # IOLoop.instance becomes self._io_loop
        self.io_loop = io_loop or IOLoop.current()
        # List of available endpoints in which service is resolved to.
        # Looks as [["host", port2], ["host2", port2]]
        self.endpoints = endpoints
        self.name = name
        self.id = generate_service_id(self)

        self.log = servicelog

        self.sessions = {}
        self.counter = itertools.count(1)
        self.api = {}

        self._lock = Lock()

        # wrap into separate class
        self.pipe = None
        self.address = None
        # on_close can be schedulled at any time,
        # even after we've already reconnected. So to prevent
        # from closing wrong connection, each new pipe has its epoch,
        # as id for on_close
        self.pipe_epoch = 0
        self.buffer = msgpack_unpacker()

        self._header_table = {
            'tx': CocaineHeaders(),
            'rx': CocaineHeaders(),
        }

    @coroutine
    def connect(self, traceid=None):
        if self._connected:
            return

        log = get_trace_adapter(self.log, traceid)
        log.debug("acquiring the connection lock")
        with (yield self._lock.acquire()):
            if self._connected:
                return

            start_time = time.time()

            if self.pipe:
                log.info("`%s` pipe has been closed by StreamClosed exception", self.name)
                self.disconnect()

            conn_statuses = []
            for host, port in self.endpoints:
                try:
                    log.info("trying %s:%d to establish connection %s", host, port, self.name)
                    self.pipe_epoch += 1
                    self.pipe = yield TCPClient(io_loop=self.io_loop).connect(host, port)
                    self.pipe.set_nodelay(True)
                    set_keep_alive(self.pipe.socket)
                    self.pipe.read_until_close(callback=functools.partial(weak_wrapper, weakref.ref(self), "on_close", self.pipe_epoch),
                                               streaming_callback=functools.partial(weak_wrapper, weakref.ref(self), "on_read"))
                except Exception as err:
                    log.error("connection error %s", err)
                    conn_statuses.append((host, port, err))
                else:
                    self.address = (host, port)
                    self._header_table = {
                        'tx': CocaineHeaders(),
                        'rx': CocaineHeaders(),
                    }

                    connection_time = (time.time() - start_time) * 1000
                    log.info("`%s` connection has been established successfully %.3fms", self.name, connection_time)
                    return

            raise ServiceConnectionError("unable to establish connection: " +
                                         ", ".join(("%s:%d %s" % (host, port, err) for (host, port, err) in conn_statuses)))

    def disconnect(self):
        self.log.debug("`%s` disconnect has been called", self.name)
        if self.pipe is None:
            return

        self.pipe.close()
        self.pipe = None

        # detach rx from sessions
        # and send errors to all of the open sessions
        sessions = self.sessions
        while sessions:
            _, rx = sessions.popitem()
            rx.error(DisconnectionError(self.name))
        self.log.info("`%s` has been disconnected", self.name)

    def on_close(self, pipe_epoch, *args):
        self.log.info("`%s` pipe has been closed with args: %s", self.name, args)
        if self.pipe_epoch == pipe_epoch:
            self.log.info("the epoch matches. Call disconnect")
            self.disconnect()

    def on_read(self, read_bytes):
        self.log.debug("read %.300s", read_bytes)
        self.buffer.feed(read_bytes)
        for msg in self.buffer:
            self.log.debug("unpacked: %.300s", msg)
            try:
                session, message_type, payload = msg[:3]  # skip extra fields
                self.log.debug("%s, %d, %.300s", session, message_type, payload)
                headers = msg[3] if len(msg) > 3 else None
            except Exception as err:
                self.log.error("malformed message: `%s` %s", err, msg)
                continue

            rx = self.sessions.get(session)
            if rx is None:
                self.log.warning("unknown session number: `%d`", session)
                continue

            rx.push(message_type, payload, headers)
            if rx.closed():
                del self.sessions[session]

    @coroutine
    def _invoke(self, method_name, *args, **kwargs):
        # Pop the Trace object, because it's not real header.
        trace = kwargs.pop("trace", None)
        if trace is not None:
            update_dict_with_trace(kwargs, trace)

        trace_id = kwargs.get('trace_id')
        trace_logger = get_trace_adapter(self.log, trace_id)
        trace_logger.debug("BaseService method `%s` call: %.300s %.300s", method_name, args, kwargs)

        yield self.connect(trace_id)

        if self.pipe is None:
            raise ServiceConnectionError('connection has suddenly disappeared')

        trace_logger.debug("%s", self.api)
        for method_id, (method, tx_tree, rx_tree) in six.iteritems(self.api):
            if method == method_name:
                trace_logger.debug("method `%s` has been found in API map", method_name)
                session = next(self.counter)  # py3 counter has no .next() method
                # Manage headers using header table.
                headers = manage_headers(kwargs, self._header_table['tx'])

                packed_data = msgpack_packb([session, method_id, args, headers])
                trace_logger.info(
                    'send message to `%s`: channel id: %s, type: %s, length: %s bytes',
                    self.name,
                    session,
                    method_name,
                    len(packed_data)
                )
                trace_logger.debug('send message: %.300s', [session, method_id, args, kwargs])

                self.pipe.write(packed_data)
                trace_logger.debug("RX TREE %s", rx_tree)
                trace_logger.debug("TX TREE %s", tx_tree)

                rx = Rx(rx_tree=rx_tree,
                        session_id=session,
                        header_table=self._header_table['rx'],
                        io_loop=self.io_loop,
                        service_name=self.name,
                        trace_id=trace_id)
                tx = Tx(tx_tree=tx_tree,
                        pipe=self.pipe,
                        session_id=session,
                        header_table=self._header_table['tx'],
                        service_name=self.name,
                        trace_id=trace_id)
                self.sessions[session] = rx
                channel = Channel(rx=rx, tx=tx)
                raise Return(channel)
        raise AttributeError(method_name)

    @property
    def _connected(self):
        return self.pipe is not None and not self.pipe.closed()

    def __getattr__(self, name):
        def on_getattr(*args, **kwargs):
            return self._invoke(six.b(name), *args, **kwargs)
        return on_getattr

    def __del__(self):
        # we have to close owned connection
        # otherwise it would be a fd-leak
        self.disconnect()

    def __str__(self):
        return "name: %s id: %s" % (self.name, self.id)

    def __repr__(self):
        return "<%s %s %s at %s>" % (type(self).__name__, self.name, self.id, hex(id(self)))
