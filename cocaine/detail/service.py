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

import datetime
import functools
import itertools
import logging
import sys
import weakref


from tornado.gen import Return
from tornado.ioloop import IOLoop
from tornado.iostream import StreamClosedError
from tornado.tcpclient import TCPClient


from .api import API
from .asyncqueue import AsyncLock
from .asyncqueue import AsyncQueue
from .util import create_new_io_loop
from .util import msgpack_packb, msgpack_unpacker

from ..common import CocaineErrno
from ..decorators import coroutine
# cocaine defined exceptions
from ..exceptions import ChokeEvent
from ..exceptions import DisconnectionError
from ..exceptions import InvalidApiVersion
from ..exceptions import InvalidMessageType
from ..exceptions import ServiceError


log = logging.getLogger("cocaine")
log.setLevel(logging.CRITICAL)

LOCATOR_DEFAULT_HOST = '127.0.0.1'
LOCATOR_DEFAULT_PORT = 10053
LOCATOR_DEFAULT_ENDPOINT = ((LOCATOR_DEFAULT_HOST, LOCATOR_DEFAULT_PORT),)

SYNC_CONNECTION_TIMEOUT = 5

if '--locator' in sys.argv:
    try:
        index = sys.argv.index('--locator') + 1
        host, _, port = sys.argv[index].rpartition(':')
        if host:
            LOCATOR_DEFAULT_HOST = host
        if port.isdigit():
            LOCATOR_DEFAULT_PORT = int(port)
    except Exception:
        pass


class EmptyResponse(object):
    pass


class ProtocolError(object):
    __slots__ = ("code", "reason")

    def __init__(self, code, reason):
        self.code = code
        self.reason = reason


def streaming_protocol(name, payload):
    if name == "write":  # pragma: no cover
        return payload[0] if len(payload) == 1 else payload
    elif name == "error":
        return ProtocolError(*payload)
    elif name == "close":
        return EmptyResponse()


def primitive_protocol(name, payload):
    if name == "value":
        return payload[0] if len(payload) == 1 else payload
    elif name == "error":
        return ProtocolError(*payload)


def null_protocol(name, payload):
    return (name, payload)


def detect_protocol_type(rx_tree):
    for name, _ in rx_tree.values():
        if name == 'value':
            return primitive_protocol
        elif name == 'write':
            return streaming_protocol
    return null_protocol


class Rx(object):
    def __init__(self, rx_tree, io_loop=None, servicename=None):
        # If it's not the main thread
        # and a current IOloop doesn't exist here,
        # IOLoop.instance becomes self._io_loop
        self._io_loop = io_loop or IOLoop.current()
        self._queue = AsyncQueue(io_loop=self._io_loop)
        self._done = False
        self.servicename = servicename
        self.rx_tree = rx_tree
        self.default_protocol = detect_protocol_type(rx_tree)

    @coroutine
    def get(self, timeout=0, protocol=None):
        if self._done and self._queue.empty():
            raise ChokeEvent()

        # to pull variuos service errors
        if timeout == 0:
            item = yield self._queue.get()
        else:
            deadline = datetime.timedelta(seconds=timeout)
            item = yield self._queue.get(deadline)

        if isinstance(item, Exception):
            raise item

        if protocol is None:
            protocol = self.default_protocol

        name, payload = item
        res = protocol(name, payload)
        if isinstance(res, ProtocolError):
            raise ServiceError(self.servicename, res.reason, res.code)
        else:
            raise Return(res)

    def done(self):
        self._done = True

    def push(self, msg_type, payload):
        dispatch = self.rx_tree.get(msg_type)
        log.debug("dispatch %s %.300s", dispatch, payload)
        if dispatch is None:
            raise InvalidMessageType(self.servicename, CocaineErrno.INVALIDMESSAGETYPE,
                                     "unexpected message type %s" % msg_type)
        name, rx = dispatch
        log.debug("name `%s` rx `%s`", name, rx)
        self._queue.put_nowait((name, payload))
        if rx == {}:  # the last transition
            self.done()
        elif rx is not None:  # not a recursive transition
            self.rx_tree = rx

    def error(self, err):
        self._queue.put_nowait(err)

    def closed(self):
        return self._done

    def __repr__(self):
        return "<%s at %s %s>" % (
            type(self).__name__, hex(id(self)), self._format())

    def __str__(self):
        return "<%s %s>" % (type(self).__name__, self._format())

    def _format(self):
        return "name: %s, queue: %s, done: %s" % (
            self.servicename, self._queue, self._done)


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

        if self.pipe is None:
            raise StreamClosedError()

        log.debug("_invoke has been called %.300s %.300s", str(args), str(kwargs))
        for method_id, (method, tx_tree) in self.tx_tree.items():  # py3 has no iteritems
            if method == method_name:
                log.debug("method `%s` has been found in API map", method_name)
                self.pipe.write(msgpack_packb([self.session_id, method_id, args]))
                if tx_tree == {}:  # last transition
                    self.done()
                elif tx_tree is not None:  # not a recursive transition
                    self.tx_tree = tx_tree
                raise Return(None)
        raise AttributeError(method_name)

    def __getattr__(self, name):
        def on_getattr(*args, **kwargs):
            return self._invoke(name, *args, **kwargs)
        return on_getattr

    def done(self):
        self._done = True

    def __repr__(self):
        return "<%s at %s %s>" % (
            type(self).__name__, hex(id(self)), self._format())

    def __str__(self):
        return "<%s %s>" % (type(self).__name__, self._format())

    def _format(self):
        return "session_id: %d, pipe: %s, done: %s" % (
            self.session_id, self.pipe, self._done)


class Channel(object):
    def __init__(self, rx, tx):
        self.rx = rx
        self.tx = tx

    def __repr__(self):
        return "<%s at %s %s>" % (
            type(self).__name__, hex(id(self)), self._format())

    def __str__(self):
        return "<%s %s>" % (type(self).__name__, self._format())

    def _format(self):
        return "tx: %s, rx: %s" % (self.tx, self.rx)


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

        self._extra = {'service': self.name,
                       'id': id(self)}
        self.log = logging.LoggerAdapter(log, self._extra)

        self.sessions = dict()
        self.counter = itertools.count(1)
        self.api = {}

        self._lock = AsyncLock()

        # wrap into separate class
        self.pipe = None
        self.address = None
        self.buffer = msgpack_unpacker()

    @coroutine
    def connect(self):
        if self._connected:
            return

        with (yield self._lock.acquire()):
            if self._connected:
                return

            for host, port in self.endpoints:
                try:
                    self.log.info("trying %s:%d to establish connection %s", host, port, self.name)
                    self.pipe = yield TCPClient(io_loop=self.io_loop).connect(host, port)
                    self.pipe.set_nodelay(True)
                    self.pipe.read_until_close(callback=functools.partial(weak_wrapper, weakref.ref(self), "on_close"),
                                               streaming_callback=functools.partial(weak_wrapper, weakref.ref(self), "on_read"))
                except Exception as err:
                    self.log.error("connection error %s", err)
                else:
                    self.address = (host, port)
                    self.log.debug("connection has been established successfully")
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

    def on_close(self, *args):
        self.log.debug("pipe has been closed %s %s", args, self.name)
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
        self.log.debug("_invoke has been called %s %s", str(args), str(kwargs))
        yield self.connect()
        self.log.debug("%s", self.api)
        for method_id, (method, tx_tree, rx_tree) in self.api.items():  # py3 has no iteritems
            if method == method_name:
                self.log.debug("method `%s` has been found in API map", method_name)
                counter = next(self.counter)  # py3 counter has no .next() method
                self.log.debug('sending message: %.300s', [counter, method_id, args])
                yield self.pipe.write(msgpack_packb([counter, method_id, args]))
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
        return self.pipe is not None

    def __getattr__(self, name):
        def on_getattr(*args, **kwargs):
            return self._invoke(name, *args, **kwargs)
        return on_getattr

    def __del__(self):
        # we have to close owned connection
        # otherwise it would be a fd-leak
        self.disconnect()


class Locator(BaseService):
    def __init__(self, endpoints=LOCATOR_DEFAULT_ENDPOINT, io_loop=None):
        super(Locator, self).__init__(name="locator",
                                      endpoints=endpoints, io_loop=io_loop)
        self.api = API.Locator


class Service(BaseService):
    def __init__(self, name, endpoints=LOCATOR_DEFAULT_ENDPOINT,
                 seed=None, version=0, locator=None, io_loop=None):
        super(Service, self).__init__(name=name, endpoints=LOCATOR_DEFAULT_ENDPOINT, io_loop=io_loop)
        self.locator_endpoints = endpoints
        self.locator = locator
        # Dispatch tree
        self.api = {}
        # Service API version
        self.version = version
        self.seed = seed

    @coroutine
    def connect(self):
        self.log.debug("checking if service connected")
        if self._connected:
            self.log.debug("already connected")
            return

        self.log.debug("resolving ...")
        # create locator here if it was not passed to us
        locator = self.locator or Locator(endpoints=self.locator_endpoints, io_loop=self.io_loop)
        try:
            if self.seed is not None:
                channel = yield locator.resolve(self.name, self.seed)
            else:
                channel = yield locator.resolve(self.name)
            # Set up self.endpoints for BaseService class
            # It's used in super(Service).connect()
            self.endpoints, version, self.api = yield channel.rx.get()
        finally:
            if self.locator is None:
                # disconnect locator as we created it
                locator.disconnect()

        self.log.debug("successfully resolved %s %s", self.endpoints, self.api)

        # Version compatibility should be checked here.
        if not (self.version == 0 or version == self.version):
            raise InvalidApiVersion(self.name, version, self.version)
        yield super(Service, self).connect()


class SyncService(object):
    def __init__(self, *args, **kwargs):
        self._io_loop = kwargs.get("io_loop") or create_new_io_loop()
        kwargs["io_loop"] = self._io_loop
        timeout = kwargs.pop("connection_timeout", SYNC_CONNECTION_TIMEOUT)
        self._service = Service(*args, **kwargs)

        # establish connection
        self._io_loop.run_sync(self._service.connect, timeout=timeout)

    def __getattr__(self, name):
        def on_getattr(*args, **kwargs):
            return self._io_loop.run_sync(lambda: self._service._invoke(name, *args, **kwargs))
        return on_getattr

    def run_sync(self, future, timeout=None):
        return self._io_loop.run_sync(lambda: future, timeout=timeout)
