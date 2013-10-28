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

import contextlib
import logging
import socket
import sys
import time
import itertools
import msgpack

from cocaine import concurrent
from cocaine.concurrent import Deferred, return_
from cocaine.asio.exceptions import *
from cocaine.asio.pipe import Pipe
from cocaine.asio.message import Message, RPC
from cocaine.asio.stream import WritableStream, ReadableStream
from cocaine.protocol import ChokeEvent

from .exceptions import ServiceError
from .session import Session
from .state import StateBuilder, RootState


__author__ = 'Evgeny Safronov <division494@gmail.com>'


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


log = logging.getLogger(__name__)

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


class strategy:
    @classmethod
    def init(cls, func, isBlocking):
        return strategy.sync(func) if isBlocking else strategy.async(func)

    @classmethod
    def coroutine(cls, func):
        def wrapper(*args, **kwargs):
            blocking = kwargs.get('blocking', False)
            return strategy.init(func, blocking)(*args, **kwargs)
        return wrapper

    @classmethod
    def sync(cls, func):
        def wrapper(*args, **kwargs):
            g = func(*args, **kwargs)
            chunk = None
            while True:
                try:
                    chunk = g.send(chunk)
                except StopIteration:
                    break
        return wrapper

    @classmethod
    def async(cls, func):
        return concurrent.engine(func)


@contextlib.contextmanager
def cumulative(timeout):
    start = time.time()

    def timeLeft():
        return timeout - (time.time() - start) if timeout is not None else None
    yield timeLeft


class scope(object):
    class socket(object):
        @classmethod
        @contextlib.contextmanager
        def blocking(cls, sock):
            try:
                sock.setblocking(True)
                yield sock
            finally:
                sock.setblocking(False)

        @classmethod
        @contextlib.contextmanager
        def timeout(cls, sock, timeout):
            try:
                sock.settimeout(timeout)
                yield sock
            finally:
                sock.settimeout(0.0)


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

        self._counter = itertools.count()
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

    # def _invoke(self, methodId):
    #     def wrapper(*args, **kwargs):
    #         deferred = Deferred()
    #         timeout = kwargs.get('timeout', None)
    #         if timeout is not None:
    #             timeoutId = self._ioLoop.add_timeout(time.time() + timeout,
    #                                                  lambda: deferred.error(TimeoutError(timeout)))
    #
    #             def timeoutRemover(func):
    #                 def wrapper(*args, **kwargs):
    #                     self._ioLoop.remove_timeout(timeoutId)
    #                     return func(*args, **kwargs)
    #                 return wrapper
    #             deferred.close = timeoutRemover(deferred.close)
    #         self._session += 1
    #         self._writableStream.write([methodId, self._session, args])
    #         self._subscribers[self._session] = deferred
    #         return deferred
    #     return wrapper

    def _invoke(self, method_id, state, *args):
        log.debug('invoking [%d, %s]', method_id, args)
        session = self._counter.next()
        deferred = self._chunk(method_id, session, *args)
        if len(state.substates) == 0:  # Non-Switching, pure invocation with deferreds and whores.
            return deferred
        else:  # Switching
            return Session(state, session, self)

    def _chunk(self, method_id, session, *args):
        log.debug('sending chunk [%d, %d, %s]', method_id, session, args)
        deferred = self.send_data(session, [method_id, session, args])
        return deferred

    def send_data(self, session, data):
        deferred = self._sessions.get(session)
        if deferred is None:
            deferred = CocaineDeferred()
            self._sessions[session] = deferred
        self._writableStream.write(data)
        return deferred

    def _make_invokable(self, state):
        def wrapper(*args, **kwargs):
            if not self.connected():
                raise IllegalStateError('service "%s" is not connected', self.name)
            return self._invoke(state.id, state, *args, **kwargs)
        return wrapper

    def _make_chunk(self, method_id, session):
        def wrapper(*args, **kwargs):
            if not self.connected():
                raise IllegalStateError('service "%s" is not connected', self.name)
            return self._chunk(method_id, session, *args, **kwargs)
        return wrapper

    def perform_sync(self, method, *args, **kwargs):
        """Performs synchronous method invocation via direct socket usage without the participation of the event loop.

        Returns generator of chunks.

        :param method: method name.
        :param args: method arguments.
        :param kwargs: method keyword arguments. You can specify `timeout` keyword to set socket timeout.

        .. note:: Left for backward compatibility, tests and other stuff. Indiscriminate using of this method can lead
                  to the summoning of Satan.
        .. warning:: Do not mix synchronous and asynchronous usage of service!
        """
        if not self.connected():
            raise IllegalStateError('service "{0}" is not connected'.format(self.name))

        if method not in self.api:
            raise ValueError('service "{0}" has no method named "{1}"'.format(self.name, method))

        timeout = kwargs.get('timeout', None)
        if timeout is not None and timeout <= 0:
            raise ValueError('timeout must be positive number')

        with scope.socket.timeout(self._pipe.sock, timeout) as sock:
            session = self._counter.next()
            sock.send(msgpack.dumps([self.api[method], session, args]))
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
                        error = ServiceError(msg.code, msg.message)


class Locator(AbstractService):
    """Represents locator service.

    Locator is the special service which can resolve other services in the cloud by name.

    .. note:: Normally, you shouldn't use this class directly - it is using behind the scene for resolving other
              services endpoints.
    """
    RESOLVE_METHOD_ID, SYNC_METHOD_ID, REPORTS_METHOD_ID, REFRESH_METHOD_ID = range(4)
    ROOT_STATE = RootState()

    def __init__(self):
        super(Locator, self).__init__('locator')
        self.api = {
            'resolve': 0
        }

    def connect(self, host, port, timeout, blocking):
        """Connects to the locator at specified host and port.

        The locator itself always runs on a well-known host and port.

        :param host: locator hostname.
        :param port: locator port.
        :param timeout: connection timeout.
        :param blocking: strategy of the connection. If flag `blocking` is set to `True`, direct blocking socket
                         connection will be used. Otherwise this method returns `cocaine.futures.chain.Chain` object,
                         which is normally requires event loop running.
        """
        return self._connect_to_endpoint(host, port, timeout, blocking=blocking)

    def resolve(self, name, timeout, blocking):
        """Resolve service by its `name`.

        Returned tuple is describing resolved service information - `(endpoint, version, api)`:
         * `endpoint` - a 2-tuple containing `(host, port)` information about service endpoint.
         * `version` - an integer number showing actual service version.
         * `api` - a dict of number -> string structure, describing service's api.

        :param name: service name.
        :param timeout: resolving timeout.
        :param blocking: strategy of the resolving. If flag `blocking` is set to `True`, direct blocking socket
                         usage will be selected. Otherwise this method returns `cocaine.futures.chain.Chain` object,
                         which is normally requires event loop running.
        """
        log.debug('resolving %s', name)
        if blocking:
            (endpoint, version, api), = [chunk for chunk in self.perform_sync('resolve', name, timeout=timeout)]
            return endpoint, version, api
        else:
            return self._invoke(self.RESOLVE_METHOD_ID, self.ROOT_STATE, name)

    def refresh(self, name, timeout=None):
        return self._invoke(self.REFRESH_METHOD_ID, self.ROOT_STATE, name)


class Service(AbstractService):
    """Represents cocaine services or applications and provides API to communicate with them.

    This is the main class you will use to manage cocaine services in python. Let's start with the simple example:

    >>> from cocaine.services import Service
    >>> node = Service('node')

    We just created `node` service object by passing its name to the `cocaine.services.Service` initialization method.
    If no errors occurred, you can use it right now.

    If the service is not available, you will see something like that:

    >>> from cocaine.services import Service
    >>> node = Service('WAT?')
    Traceback (most recent call last):
    ...
    cocaine.exceptions.ServiceError: error in service "locator" - the specified service is not available [1]

    Behind the scene it has synchronously connected to the locator, resolved service's API and connected to the
    service's endpoint obtained by resolving. This is the normal usage of services.

    If you don't want immediate blocking service initialization, you can set `blockingConnect` argument to `False`
    and then to connect manually:

    >>> from cocaine.services import Service
    >>> node = Service('node', blockingConnect=False)
    >>> node.connect()

    You can also specify locator's address by passing `host` and `port` parameters like this:

    >>> from cocaine.services import Service
    >>> node = Service('node', host='localhost', port=666)

    .. note:: If you refused service connection-at-initialization, you shouldn't pass locator endpoint information,
              because this is mutual exclusive information. Specify them later when `connect` while method invoking.

    .. note:: If you don't want to create connection to the locator each time you create service, you can use
              `connectThroughLocator` method, which is specially designed for that cases.

    .. note:: Actual service's API is building dynamically. Sorry, IDE users, there is no autocompletion :(

    :ivar name: service or application name.
    :ivar version: service or application version. Provided only after its resolving.
    :ivar api: service or application API. Provided only after its resolving.
    """
    _locator_cache = {}

    def __init__(self, name, blockingConnect=True, host=LOCATOR_DEFAULT_HOST, port=LOCATOR_DEFAULT_PORT):
        super(Service, self).__init__(name)

        if not blockingConnect and any([host != LOCATOR_DEFAULT_HOST, port != LOCATOR_DEFAULT_PORT]):
            raise ValueError('you should not specify locator address in __init__ while performing non-blocking connect')

        if blockingConnect:
            self.connect(host, port, blocking=True)

    @strategy.coroutine
    def connect(self, host=LOCATOR_DEFAULT_HOST, port=LOCATOR_DEFAULT_PORT, timeout=None, blocking=False):
        """Connect to the service through locator and initialize its API.

        Before service is connected to its endpoint there is no any API (cause it's provided by locator). Any usage of
        uninitialized service results in `IllegalStateError`.

        .. note:: Note, that locator connection is created (and destroyed) each time you invoke this method.
                  If you don't want to create connection to the locator each time you create service, you can use
                  `connectThroughLocator` method, which is specially designed for that cases.
        """
        if (host, port) not in self._locator_cache:
            locator = Locator()
            self._locator_cache[(host, port)] = locator
        else:
            locator = self._locator_cache[(host, port)]

        if not locator.connected():
            yield locator.connect(host, port, timeout, blocking=blocking)
        yield self.connectThroughLocator(locator, timeout, blocking=blocking)

    @strategy.coroutine
    def connectThroughLocator(self, locator, timeout=None, blocking=False):
        try:
            endpoint, self.version, api = yield locator.resolve(self.name, timeout, blocking=blocking)
        except ServiceError as err:
            raise LocatorResolveError(self.name, locator.address, err)

        self.states = StateBuilder.build(api).substates
        for state in self.states.values():
            self.api[state.name] = state.id
            invoke = self._make_invokable(state)
            # invoke = self._make_reconnectable(invoke, locator)
            setattr(self, state.name, invoke)

        yield self._connect_to_endpoint(*endpoint, timeout=timeout, blocking=blocking)

    def _make_reconnectable(self, func, locator):
        @strategy.coroutine
        def wrapper(*args, **kwargs):
            if not self.connected():
                yield self.connectThroughLocator(locator)

            try:
                d = yield func(*args, **kwargs)
            except KeyError as fd:
                log.warn('broken pipe detected, fd: %s', str(fd))
                log.info('reconnecting... ')
                yield self.disconnect()
                yield self.connectThroughLocator(locator)
                d = yield func(*args, **kwargs)
                log.info('service has been successfully reconnected')
            return_(d)

        return wrapper

    @strategy.coroutine
    def reconnect(self, timeout=None, blocking=False):
        if self.connecting():
            raise IllegalStateError('already connecting')
        self.disconnect()
        yield self.connect(timeout=timeout, blocking=blocking)

    def __getattr__(self, item):
        def caller(*args, **kwargs):
            return self.enqueue(item, *args, **kwargs)
        return caller
