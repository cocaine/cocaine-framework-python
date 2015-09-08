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
import logging
import time
import weakref

from tornado.gen import Return
from tornado.ioloop import IOLoop
from tornado.locks import Lock
from tornado.tcpclient import TCPClient


from .channel import Channel
from .channel import Rx
from .channel import Tx
from .log import servicelog
from .trace import pack_trace
from .util import generate_service_id, msgpack_packb, msgpack_unpacker
from ..decorators import coroutine
from ..exceptions import DisconnectionError


class TraceAdapter(logging.LoggerAdapter):
    def process(self, msg, kwargs):
        return '%s\t%s' % (self.extra["traceid"], msg), kwargs


def weak_wrapper(weak_service, method_name, *args, **kwargs):
    service = weak_service()
    if service is None:
        return

    return getattr(service, method_name)(*args, **kwargs)


class BaseService(object):
    def __init__(self, name, endpoints, io_loop=None):
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

        self.sessions = dict()
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

    @coroutine
    def connect(self, traceid=None):
        if self._connected:
            return

        log = TraceAdapter(self.log, {"traceid": traceid}) if traceid else self.log

        log.info("acquiring the connection lock")
        with (yield self._lock.acquire()):
            if self._connected:
                return

            start_time = time.time()

            for host, port in self.endpoints:
                try:
                    log.info("trying %s:%d to establish connection %s", host, port, self.name)
                    self.pipe_epoch += 1
                    pipe_epoch = self.pipe_epoch
                    self.pipe = yield TCPClient(io_loop=self.io_loop).connect(host, port)
                    self.pipe.set_nodelay(True)
                    self.pipe.read_until_close(callback=functools.partial(weak_wrapper, weakref.ref(self), "on_close", pipe_epoch),
                                               streaming_callback=functools.partial(weak_wrapper, weakref.ref(self), "on_read"))
                except Exception as err:
                    log.error("connection error %s", err)
                else:
                    self.address = (host, port)
                    connection_time = (time.time() - start_time) * 1000
                    log.info("connection has been established successfully %.3fms" % connection_time)
                    return

            raise Exception("unable to establish connection")

    def disconnect(self):
        self.log.debug("disconnect has been called %s", self.name)
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

    def on_close(self, pipe_epoch, *args):
        self.log.debug("pipe has been closed %s %s", args, self.name)
        if self.pipe_epoch == pipe_epoch:
            self.log.debug("the epoch matches. Call disconnect")
            self.disconnect()

    def on_read(self, read_bytes):
        self.log.debug("read %.300s", read_bytes)
        self.buffer.feed(read_bytes)
        for msg in self.buffer:
            self.log.debug("unpacked: %.300s", msg)
            try:
                session, message_type, payload = msg[:3]  # skip extra fields
                self.log.debug("%s, %d, %.300s", session, message_type, payload)
            except Exception as err:
                self.log.error("malformed message: `%s` %s", err, str(msg))
                continue

            rx = self.sessions.get(session)
            if rx is None:
                self.log.warning("unknown session number: `%d`", session)
                continue

            rx.push(message_type, payload)
            if rx.closed():
                del self.sessions[session]

    @coroutine
    def _invoke(self, method_name, *args, **kwargs):
        self.log.debug("_invoke has been called %.300s %.300s", str(args), str(kwargs))
        trace = kwargs.get("trace")
        if trace:
            yield self.connect(hex(trace.traceid)[2:])
        else:
            yield self.connect()
        self.log.debug("%s", self.api)
        for method_id, (method, tx_tree, rx_tree) in self.api.items():  # py3 has no iteritems
            if method == method_name:
                self.log.debug("method `%s` has been found in API map", method_name)
                counter = next(self.counter)  # py3 counter has no .next() method
                self.log.debug('sending message: %.300s', [counter, method_id, args])
                if trace is None:
                    self.pipe.write(msgpack_packb([counter, method_id, args]))
                else:
                    self.pipe.write(msgpack_packb([counter, method_id, args, pack_trace(trace)]))
                self.log.debug("RX TREE %s", rx_tree)
                self.log.debug("TX TREE %s", tx_tree)

                rx = Rx(rx_tree, io_loop=self.io_loop, servicename=self.name)
                tx = Tx(tx_tree, self.pipe, counter)
                self.sessions[counter] = rx
                channel = Channel(rx=rx, tx=tx)
                raise Return(channel)
        raise AttributeError(method_name)

    @property
    def _connected(self):
        return self.pipe is not None and not self.pipe.closed()

    def __getattr__(self, name):
        def on_getattr(*args, **kwargs):
            return self._invoke(name, *args, **kwargs)
        return on_getattr

    def __del__(self):
        # we have to close owned connection
        # otherwise it would be a fd-leak
        self.disconnect()

    def __str__(self):
        return "name: %s id: %s" % (self.name, self.id)

    def __repr__(self):
        return "<%s %s %s at %s>" % (
            type(self).__name__, self.name, self.id, hex(id(self)))
