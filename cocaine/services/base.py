#
#    Copyright (c) 2013+ Evgeny Safronov <division494@gmail.com>
#    Copyright (c) 2011-2013 Other contributors as noted in the AUTHORS file.
#
#    This file is part of Cocaine.
#
#    Cocaine is free software; you can redistribute it and/or modify
#    it under the terms of the GNU Lesser General Public License as published
#    by the Free Software Foundation; either version 3 of the License, or
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
import msgpack
import socket
import sys
import time

from tornado import stack_context
from tornado.ioloop import IOLoop

from ..asio.stream import CocaineStream
from ..asio.exceptions import ConnectError, TimeoutError
from ..concurrent import Deferred
from ..exceptions import IllegalStateError
from ..protocol import ChokeEvent
from ..protocol.message import Message, RPC

from .exceptions import ServiceError
from .session import Session

__author__ = 'Evgeny Safronov <division494@gmail.com>'


log = logging.getLogger(__name__)


class ResolveError(IOError):
    pass


class CocaineDeferred(Deferred):
    def __init__(self):
        super(CocaineDeferred, self).__init__()
        self.count = 0
        self.closed = False

    def _trigger(self, result):
        self.count += 1
        super(CocaineDeferred, self)._trigger(result)

    def close(self):
        if self.count == 0:
            self.trigger()
        else:
            self.error(ChokeEvent())
        super(CocaineDeferred, self).close()


# todo: Make defaults namespace
LOCATOR_DEFAULT_HOST = '127.0.0.1'
LOCATOR_DEFAULT_PORT = 10053

if '--locator' in sys.argv:
    index = sys.argv.index('--locator') + 1
    host, _, port = sys.argv[index].rpartition(':')
    if host:
        LOCATOR_DEFAULT_HOST = host
    if port.isdigit():
        LOCATOR_DEFAULT_PORT = int(port)


class ServiceConnector(object):
    class Timeout(object):
        def __init__(self, value):
            self.value = value
            self.id = 0

    def __init__(self, host, port, timeout=None, io_loop=None):
        self.host = host
        self.port = port
        self.timeout = self.Timeout(timeout) if timeout is not None else None
        self.io_loop = io_loop or IOLoop.current()

        self.deferred = None

    def connect(self):
        if self.deferred is not None:
            return self.deferred

        log.debug('connecting to %s:%d', self.host, self.port)
        candidates = socket.getaddrinfo(self.host, self.port, 0, socket.SOCK_STREAM)
        if not candidates:
            log.warn('could not resolve %s:%d', self.host, self.port)
            raise ResolveError()

        log.debug('candidates: %s', candidates)

        self.deferred = Deferred()
        if self.timeout is not None:
            deadline = time.time() + self.timeout.value
            self.timeout.id = self.io_loop.add_timeout(deadline, self._handle_connection_timeout)

        df = self._try_connect(candidates[0])
        df.add_callback(stack_context.wrap(functools.partial(self._handle_connection, candidates=candidates[1:])))
        return self.deferred

    def _try_connect(self, candidate):
        family, socktype, proto, canonname, address = candidate
        log.debug(' - trying [%d] %s', proto, address)
        deferred = Deferred()
        try:
            sock = socket.socket(family=family, type=socktype, proto=proto)
            self._stream = CocaineStream(sock, io_loop=self.io_loop)
            self._stream.connect(address, callback=deferred.trigger)
            self._stream.set_close_callback(functools.partial(self._handle_connection_error, deferred))
        except Exception as err:
            log.warn(' - failed: %s', err)
            deferred.error(err)
        return deferred

    def _handle_connection(self, future, candidates):
        try:
            future.get()
        except Exception as err:
            log.warn(' - failed: %s', err)
            if candidates:
                df = self._try_connect(candidates[0])
                callback = stack_context.wrap(functools.partial(self._handle_connection, candidates=candidates[1:]))
                df.add_callback(callback)
            else:
                df = self.deferred
                self.deferred = None
                df.error(ConnectError())
        else:
            log.debug(' - success')
            if self.timeout is not None:
                self.io_loop.remove_timeout(self.timeout.id)
                self.timeout = None
            self._stream.set_close_callback(None)
            df = self.deferred
            self.deferred = None
            df.trigger(self._stream)

    def _handle_connection_error(self, deferred):
        deferred.error(ConnectError(self._stream.error))

    def _handle_connection_timeout(self):
        self.io_loop.remove_timeout(self.timeout.id)
        self.timeout = None
        self.deferred.error(TimeoutError())


class Decoder(object):
    def __init__(self):
        self._unpacker = msgpack.Unpacker()
        self._callback = None

    def set_callback(self, callback):
        self._callback = callback

    def feed(self, data):
        self._unpacker.feed(data)
        if self._callback is None:
            return

        for chunk in self._unpacker:
            self._callback(chunk)


class AbstractService(object):
    """Represents abstract cocaine service.

    It provides basic service operations like getting its actual network address, determining if the service is
    connecting or connected.

    There is no other useful public methods, so the main aim of this class - is to provide superclass for inheriting
    for actual services or service-like objects (i.e. Locator).

    :ivar name: service name.
    """
    def __init__(self, name):
        self.name = name

        self._stream = None
        self._decoder = None

        self._counter = itertools.count(1)
        self._sessions = {}

        self.version = 0
        self.api = {}
        self.states = []

    @property
    def address(self):
        """Return actual network address (`sockaddr`) of the current service if it is connected.

        Returned `sockaddr` is a tuple describing a socket address, whose format depends on the returned
        family `(address, port)` 2-tuple for AF_INET, or `(address, port, flow info, scope id)` 4-tuple for AF_INET6),
        and is meant to be passed to the socket.connect() method.

        It the service is not connected this method returns tuple `('0.0.0.0', 0)`.
        """
        if self._stream is not None:
            return self._stream.socket.getsockname()
        else:
            return '0.0.0.0', 0

    def connecting(self):
        """Return true if the service is in connecting state."""
        return self._stream is not None and not self._stream.closed() and self._stream._connecting

    def connected(self):
        """Return true if the service is in connected state."""
        return self._stream is not None and not self._stream.closed() and not self.connecting()

    def disconnect(self):
        """Disconnect service from its endpoint and destroys all communications between them.

        .. note:: This method does nothing if the service is not connected.
        """
        if not self._stream:
            return
        self._stream.close()
        self._stream = None

    def _connect_to_endpoint(self, host, port, timeout):
        log.debug('connecting to the service "%s"', self.name)
        if self.connected():
            raise IllegalStateError('service "%s" is already connected', self.name)

        deferred = ServiceConnector(host, port, timeout).connect()
        deferred.add_callback(self._on_connect)
        return deferred

    def _on_connect(self, future):
        try:
            self._stream = future.get()
        except Exception as err:
            log.warn('err: %s', err)
        else:
            log.debug('successfully connected')
            self._stream.set_read_callback(self._on_message)

    def _on_message(self, args):
        message = Message.initialize(args)
        assert message.id in (RPC.CHUNK, RPC.ERROR, RPC.CHOKE), 'unexpected message id: {0}'.format(message.id)

        deferred = self._sessions[message.session]
        if message.id == RPC.CHUNK:
            chunk = msgpack.loads(message.data)
            deferred.trigger(chunk)
        elif message.id == RPC.ERROR:
            deferred.error(ServiceError(message.errno, message.reason))
        elif message.id == RPC.CHOKE:
            self._sessions.pop(message.session)
            deferred.close()

    def _invoke(self, method_id, state, *args):
        log.debug('invoking [%d, %s]', method_id, args)
        session = self._counter.next()
        deferred = self._chunk(method_id, session, *args)
        if len(state.substates) == 0:  # Non-Switching, pure invocation with deferreds and whores.
            return deferred
        else:  # Switching
            return Session(state, session, self, deferred)

    def _chunk(self, method_id, session, *args):
        log.debug('sending chunk [%d, %d, %s]', method_id, session, args)
        deferred = self.send_data(session, [method_id, session, args])
        return deferred

    def send_data(self, session, data):
        deferred = self._sessions.get(session)
        if deferred is None:
            deferred = CocaineDeferred()
            self._sessions[session] = deferred
        if self._stream:
            self._stream.write(msgpack.dumps(data))
        return deferred