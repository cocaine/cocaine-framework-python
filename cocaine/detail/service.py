#
#    Copyright (c) 2012+ Anton Tyurin <noxiouz@yandex.ru>
#    Copyright (c) 2013+ Evgeny Safronov <division494@gmail.com>
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

import itertools
import logging
import sys


import msgpack
from tornado.gen import Return
from tornado.tcpclient import TCPClient
from tornado.ioloop import IOLoop


from .api import API
from .asyncqueue import AsyncQueue
from .asyncqueue import AsyncLock
from ..common import CocaineErrno
from ..decorators import coroutine

# cocaine defined exceptions
from ..exceptions import ChokeEvent
from ..exceptions import DisconnectionError
from ..exceptions import InvalidMessageType
from ..exceptions import InvalidApiVersion
from ..exceptions import ServiceError


log = logging.getLogger("cocaine")


class EmptyResponse(object):
    pass


def StreamingProtocol(name, payload):
    if name == "write":
        if len(payload) == 1:
            return payload[0]
        else:
            return payload
    elif name == "error":
        return ServiceError(*payload)
    elif name == "close":
        return EmptyResponse()


def PrimitiveProtocol(name, payload):
    if name == "value":
        if len(payload) == 1:
            return payload[0]
        else:
            return payload
    elif name == "error":
        return ServiceError(*payload)


def NullProtocol(name, payload):
    return (name, payload)


def detect_protocol_type(rx_tree):
    for name, _ in rx_tree.values():
        if name in ('value'):
            return PrimitiveProtocol
        elif name in ('write'):
            return StreamingProtocol
    return NullProtocol


class Rx(object):
    def __init__(self, rx_tree):
        self._queue = AsyncQueue()
        self._done = False
        self.rx_tree = rx_tree
        self.default_protocol = detect_protocol_type(rx_tree)

    @coroutine
    def get(self, timeout=0, protocol=None):
        if self._done and self._queue.empty():
            raise ChokeEvent()

        # to pull variuos service errors
        item = yield self._queue.get()
        if isinstance(item, Exception):
            raise item

        if protocol is None:
            protocol = self.default_protocol

        name, payload = item
        res = protocol(name, payload)
        if isinstance(res, Exception):
            raise res
        else:
            raise Return(res)

    def done(self):
        self._done = True

    def push(self, msg_type, payload):
        dispatch = self.rx_tree.get(msg_type)
        log.debug("dispatch %s %s", dispatch, payload)
        if dispatch is None:
            raise InvalidMessageType(CocaineErrno.INVALIDMESSAGETYPE,
                                     "unexpected message type %s" % msg_type)
        name, rx = dispatch
        log.debug("name `%s` rx `%s`", name, rx)
        self._queue.put_nowait((name, payload))
        if rx == {}:  # last transition
            self.done()
        elif rx is not None:  # not a recursive transition
            self.rx_tree = rx

    def error(self, err):
        self._queue.put_nowait(err)


class Tx(object):
    def __init__(self, tx_tree, pipe, session_id):
        self.tx_tree = tx_tree
        self.session_id = session_id
        self.pipe = pipe
        self._done = False

    @coroutine
    def _invoke(self, method_name, *args, **kwargs):
        if self._done:
            raise ChokeEvent()

        log.debug("_invoke has been called %s %s", str(args), str(kwargs))
        for method_id, (method, tx_tree) in self.tx_tree.items():  # py3 has no iteritems
            if method == method_name:
                log.debug("method `%s` has been found in API map", method_name)
                self.pipe.write(msgpack.packb([self.session_id, method_id, args]))
                if tx_tree == {}:  # last transition
                    self.done()
                elif tx_tree is not None:  # not a recursive transition
                    self.tx_tree = tx_tree
                raise Return(None)
        raise AttributeError("method_name")

    def __getattr__(self, name):
        def on_getattr(*args, **kwargs):
            return self._invoke(name, *args, **kwargs)
        return on_getattr

    def done(self):
        self._done = True


class Channel(object):
    def __init__(self, rx, tx):
        self.rx = rx
        self.tx = tx


class BaseService(object):
    # py3: msgpack by default unpacks strings as bytes.
    # Make it to unpack as strings for compatibility.
    _msgpack_string_encoding = None if sys.version_info[0] == 2 else 'utf8'

    def __init__(self, name, host='localhost', port=10053, loop=None):
        self.loop = loop or IOLoop.current()
        # List of available endpoints in which service is resolved to.
        # Looks as [["host", port2], ["host2", port2]]
        self.endpoints = [[host, port]]
        self.name = name

        self._extra = {'service': self.name,
                       'id': id(self)}
        self.log = logging.LoggerAdapter(log, self._extra)

        self.sessions = {}
        self.counter = itertools.count(1)
        self.api = {}

        self._lock = AsyncLock()

        # wrap into separate class
        self.pipe = None
        self.address = None
        self.buffer = msgpack.Unpacker(encoding=self._msgpack_string_encoding)

    @coroutine
    def connect(self):
        if self._connected:
            raise Return(True)

        with (yield self._lock.acquire()):
            if self._connected:
                raise Return(True)

            for host, port in self.endpoints:
                try:
                    self.log.info("trying %s:%d to establish connection", host, port)
                    self.pipe = yield TCPClient(io_loop=self.loop).connect(host, port)
                    self.pipe.set_nodelay(True)
                    self.pipe.read_until_close(callback=self.on_close,
                                               streaming_callback=self.on_read)
                except Exception as err:
                    self.log.error("connection error %s", err)
                else:
                    self.address = (host, port)
                    self.log.debug("connection has been established successfully")
                    raise Return(True)

            raise Exception("unable to establish connection")

    def disconnect(self):
        if self.pipe is None:
            return

        self.pipe.set_close_callback(lambda x: None)
        self.pipe.close()
        self.pipe = None

        for session_rx in self.sessions.values():
            session_rx.error(DisconnectionError(self.name))

    def on_close(self, *args):
        self.log.debug("pipe has been closed %s", args)
        self.disconnect()

    def on_read(self, read_bytes):
        self.log.debug("read %s", read_bytes)
        self.buffer.feed(read_bytes)
        for msg in self.buffer:
            self.log.debug("unpacked: %s", msg)
            try:
                session, message_type, payload = msg
                self.log.debug("%s, %d, %s", session, message_type, payload)
            except Exception as err:
                self.log.error("malformed message: `%s` %s", err, str(msg))
                continue

            rx = self.sessions.get(session)
            if rx is None:
                self.log.warning("unknown session number: `%d`", session)
                continue

            rx.push(message_type, payload)

    @coroutine
    def _invoke(self, method_name, *args, **kwargs):
        self.log.debug("_invoke has been called %s %s", str(args), str(kwargs))
        yield self.connect()
        self.log.debug("%s", self.api)
        for method_id, (method, tx_tree, rx_tree) in self.api.items():  # py3 has no iteritems
            if method == method_name:
                self.log.debug("method `%s` has been found in API map", method_name)
                counter = next(self.counter)  # py3 counter has no .next() method
                self.log.debug('sending message: %s', [counter, method_id, args])
                self.pipe.write(msgpack.packb([counter, method_id, args]))
                self.log.debug("RX TREE %s", rx_tree)
                self.log.debug("TX TREE %s", tx_tree)

                rx = Rx(rx_tree)
                tx = Tx(tx_tree, self.pipe, counter)
                self.sessions[counter] = rx
                channel = Channel(rx=rx, tx=tx)
                raise Return(channel)
        raise AttributeError(method_name)

    @property
    def _connected(self):
        return self.pipe is not None

    def __getattr__(self, name):
        def on_getattr(*args, **kwargs):
            return self._invoke(name, *args, **kwargs)
        return on_getattr


class Locator(BaseService):
    def __init__(self, host="localhost", port=10053, loop=None):
        super(Locator, self).__init__(name="locator",
                                      host=host, port=port, loop=loop)
        self.api = API.Locator


class Service(BaseService):
    def __init__(self, name, seed=None, host="localhost", port=10053, version=0, loop=None):
        super(Service, self).__init__(name=name, loop=loop)
        self.locator = Locator(host=host, port=port, loop=loop)
        # Dispatch tree
        self.api = {}
        # Service API version
        self.version = version
        self.seed = seed

    @coroutine
    def connect(self):
        self.log.debug("checking if service connected", extra=self._extra)
        if self._connected:
            log.debug("already connected", extra=self._extra)
            return

        self.log.debug("resolving ...", extra=self._extra)
        if self.seed is not None:
            channel = yield self.locator.resolve(self.name, self.seed)
        else:
            channel = yield self.locator.resolve(self.name)
        # Set up self.endpoints for BaseService class
        # It's used in super(Service).connect()
        self.endpoints, version, self.api = yield channel.rx.get()
        self.log.debug("successfully resolved %s %s", self.endpoints,
                       self.api, extra=self._extra)

        # Version compatibility should be checked here.
        if not (self.version == 0 or version == self.version):
            raise InvalidApiVersion(self.name, version, self.version)
        yield super(Service, self).connect()
