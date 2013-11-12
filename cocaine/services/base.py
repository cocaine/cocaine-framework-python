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

import itertools
import logging
import msgpack
import socket
import sys
import time

from ..asio.exceptions import ConnectionResolveError, ConnectionError, ConnectionTimeoutError
from ..asio.pipe import Pipe
from ..asio.stream import WritableStream, ReadableStream
from ..concurrent import Deferred
from ..exceptions import IllegalStateError
from ..protocol import ChokeEvent
from ..protocol.message import Message, RPC

from .exceptions import ServiceError
from .internal import strategy, scope
from .session import Session

__author__ = 'Evgeny Safronov <division494@gmail.com>'


log = logging.getLogger(__name__)


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


# Make defaults namespace
LOCATOR_DEFAULT_HOST = '127.0.0.1'
LOCATOR_DEFAULT_PORT = 10053

if '--locator' in sys.argv:
    index = sys.argv.index('--locator') + 1
    host, _, port = sys.argv[index].rpartition(':')
    if host:
        LOCATOR_DEFAULT_HOST = host
    if port.isdigit():
        LOCATOR_DEFAULT_PORT = int(port)


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

        self._pipe = None
        self._ioLoop = None
        self._writableStream = None
        self._readableStream = None

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

        It the service is not connected this method returns tuple `('NOT_CONNECTED', 0)`.
        """
        return self._pipe.address if self.connected() else ('NOT_CONNECTED', 0)

    def connecting(self):
        """Return true if the service is in connecting state."""
        return self._pipe is not None and self._pipe.isConnecting()

    def connected(self):
        """Return true if the service is in connected state."""
        return self._pipe is not None and self._pipe.isConnected()

    def disconnect(self):
        """Disconnect service from its endpoint and destroys all communications between them.

        .. note:: This method does nothing if the service is not connected.
        """
        if not self._pipe:
            return
        self._pipe.close()
        self._pipe = None

    @strategy.coroutine
    def _connect_to_endpoint(self, host, port, timeout, blocking=False):
        if self.connected():
            raise IllegalStateError('service "{0}" is already connected'.format(self.name))

        addressInfoList = socket.getaddrinfo(host, port, 0, socket.SOCK_STREAM)
        if not addressInfoList:
            raise ConnectionResolveError((host, port))

        pipe_timeout = float(timeout) / len(addressInfoList) if timeout is not None else None

        log.debug('Connecting to the service "{0}", candidates: {1}'.format(self.name, addressInfoList))
        start = time.time()
        errors = []
        for family, socktype, proto, canonname, address in addressInfoList:
            log.debug(' - connecting to "{0} {1}"'.format(proto, address))
            sock = socket.socket(family=family, type=socktype, proto=proto)
            try:
                self._pipe = Pipe(sock)
                yield self._pipe.connect(address, timeout=pipe_timeout, blocking=blocking)
                log.debug(' - success')
            except ConnectionError as err:
                errors.append(err)
                log.debug(' - failed - {0}'.format(err))
            except Exception as err:
                log.warn('Unexpected error caught while connecting to the "{0}" - {1}'.format(address, err))
            else:
                self._ioLoop = self._pipe._ioLoop
                self._writableStream = WritableStream(self._ioLoop, self._pipe)
                self._readableStream = ReadableStream(self._ioLoop, self._pipe)
                self._ioLoop.bind_on_fd(self._pipe.fileno())

                def decode_and_dispatch(on_event):
                    def dispatch(unpacker):
                        for chunk in unpacker:
                            on_event(chunk)
                    return dispatch
                self._readableStream.bind(decode_and_dispatch(self._on_message))
                return

        if timeout is not None and time.time() - start > timeout:
            raise ConnectionTimeoutError((host, port), timeout)

        prefix = 'service resolving failed. Reason:'
        reason = '{0} [{1}]'.format(prefix, ', '.join(str(err) for err in errors))
        raise ConnectionError((host, port), reason)

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
        self._writableStream.write(msgpack.dumps(data))
        return deferred

    def _invoke_sync(self, method, *args, **kwargs):
        """Performs synchronous method invocation via direct socket usage without the participation of the event loop.

        Returns generator of chunks.

        :param method: method name.
        :param args: method arguments.
        :param kwargs: method keyword arguments. You can specify `timeout` keyword to set socket timeout.

        .. note:: Left for backward compatibility, tests and other stuff. Indiscriminate using of this method can lead
                  to the summoning of Satan.
        .. warning:: Do not mix synchronous and asynchronous usage of service!
        """
        if method not in self.api:
            raise ValueError('service "{0}" has no method named "{1}"'.format(self.name, method))

        return self._invoke_sync_by_id(self.api[method], *args, **kwargs)

    def _invoke_sync_by_id(self, method_id, *args, **kwargs):
        if not self.connected():
            raise IllegalStateError('service "{0}" is not connected'.format(self.name))

        timeout = kwargs.get('timeout', None)
        if timeout is not None and timeout <= 0:
            raise ValueError('timeout must be positive number')

        with scope.socket.timeout(self._pipe.sock, timeout) as sock:
            session = self._counter.next()
            sock.send(msgpack.dumps([method_id, session, args]))
            unpacker = msgpack.Unpacker()
            error = None
            while True:
                data = sock.recv(4096)
                unpacker.feed(data)
                for chunk in unpacker:
                    msg = Message.initialize(chunk)
                    if msg is None:
                        continue
                    if msg.id == RPC.CHUNK:
                        yield msgpack.loads(msg.data)
                    elif msg.id == RPC.CHOKE:
                        raise error or StopIteration
                    elif msg.id == RPC.ERROR:
                        error = ServiceError(msg.errno, msg.reason)
