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
import sys

from ..asio.connector import Connector
from ..concurrent import Deferred
from ..exceptions import IllegalStateError
from ..protocol import ChokeEvent
from ..protocol.message import Message, RPC

from .exceptions import ServiceError
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
        if self.connected():
            return self._stream.address()
        else:
            return '0.0.0.0', 0

    def connecting(self):
        """Return true if the service is in connecting state."""
        return self._stream is not None and self._stream.connecting()

    def connected(self):
        """Return true if the service is in connected state."""
        return self._stream is not None and self._stream.connected()

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

        deferred = Connector(host, port, timeout).connect()
        deferred.add_callback(self._on_connect)
        return deferred

    def _on_connect(self, future):
        try:
            self._stream = future.get()
        except Exception as err:
            log.warn('failed to connect: %s', err)
        else:
            log.debug('successfully connected')
            self._stream.set_read_callback(self._on_message)
            self._stream.set_close_callback(self._on_disconnect)

    def _on_disconnect(self):
        #todo: anyway we need to drop all sessions.
        if self._stream is not None and self._stream.socket is not None:
            log.warn('service "%s" has been disconnected: %s', self.name, self._stream.error)
        else:
            log.debug('service "%s" has been disconnected', self.name)

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
        deferred = self._push(method_id, session, *args)
        if len(state.substates) == 0:  # Non-Switching, pure invocation with deferreds and whores.
            return deferred
        else:  # Switching
            return Session(state, session, self, deferred)

    def _push(self, method_id, session, *args):
        log.debug('sending chunk [%d, %d, %s]', method_id, session, args)
        deferred = self._send_data(session, [method_id, session, args])
        return deferred

    def _send_data(self, session, data):
        deferred = self._sessions.get(session)
        if deferred is None:
            deferred = CocaineDeferred()
            self._sessions[session] = deferred
        if self._stream:
            self._stream.write(msgpack.dumps(data))
        return deferred