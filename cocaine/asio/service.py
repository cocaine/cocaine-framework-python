import logging
import socket
from time import time
from contextlib import contextmanager

import msgpack

from cocaine.exceptions import ServiceError
from cocaine.asio.exceptions import *
from cocaine.asio.pipe import Pipe
from cocaine.asio import message
from cocaine.asio.message import Message
from cocaine.asio.stream import Decoder, WritableStream, ReadableStream
from cocaine.futures import Future, chain
from cocaine.futures.chain import Chain


__author__ = 'Evgeny Safronov <division494@gmail.com>'


log = logging.getLogger(__name__)

LOCATOR_DEFAULT_HOST = '127.0.0.1'
LOCATOR_DEFAULT_PORT = 10053


class strategy:
    @classmethod
    def init(cls, func, isBlocking):
        return strategy.sync(func) if isBlocking else strategy.async(func)

    @classmethod
    def sync(cls, func):
        def wrapper(*args, **kwargs):
            coroutine = func(*args, **kwargs)
            chunk = None
            while True:
                try:
                    chunk = coroutine.send(chunk)
                except StopIteration:
                    break
        return wrapper

    @classmethod
    def async(cls, func):
        return chain.source(func)


@contextmanager
def cumulative(timeout):
    start = time()

    def timeLeft():
        return timeout - (time() - start) if timeout is not None else None
    yield timeLeft


class scope(object):
    class socket(object):
        @classmethod
        @contextmanager
        def blocking(cls, sock):
            try:
                sock.setblocking(True)
                yield sock
            finally:
                sock.setblocking(False)

        @classmethod
        @contextmanager
        def timeout(cls, sock, timeout):
            try:
                sock.settimeout(timeout)
                yield sock
            finally:
                sock.settimeout(0.0)


class AbstractService(object):
    def __init__(self, name, isBlocking):
        self.name = name
        self.isBlocking = isBlocking
        self._connectToEndpoint = strategy.init(self._connectToEndpoint, isBlocking)

        self._pipe = None
        self._ioLoop = None
        self._writableStream = None
        self._readableStream = None

        self.decoder = Decoder()
        self.decoder.bind(self._on_message)

        self._subscribers = {}
        self._session = 0

        self.api = {}

    @property
    def address(self):
        return self._pipe.address if self.isConnected() else 'unknown'

    def isConnected(self):
        return self._pipe is not None and self._pipe.isConnected()

    def _connectToEndpoint(self, host, port, timeout=None):
        if self.isConnected():
            raise IllegalStateError('service "{0}" is already connected'.format(self.name))

        addressInfoList = socket.getaddrinfo(host, port, 0, socket.SOCK_STREAM)
        if not addressInfoList:
            raise ConnectionResolveError((host, port))

        start = time()
        errors = []
        for family, socktype, proto, canonname, address in addressInfoList:
            sock = socket.socket(family=family, type=socktype, proto=proto)
            try:
                self._pipe = Pipe(sock)
                remainingTimeout = timeout - (time() - start) if timeout is not None else None
                yield self._pipe.connect(address, timeout=remainingTimeout, blocking=self.isBlocking)
            except ConnectionError as err:
                errors.append(err)
            else:
                self._ioLoop = self._pipe._ioLoop
                self._writableStream = WritableStream(self._ioLoop, self._pipe)
                self._readableStream = ReadableStream(self._ioLoop, self._pipe)
                self._ioLoop.bind_on_fd(self._pipe.fileno())
                self._readableStream.bind(self.decoder.decode)
                return

        if timeout is not None and time() - start > timeout:
            raise ConnectionTimeoutError((host, port), timeout)

        reason = 'multiple connection errors: ' + ', '.join(err.message for err in errors)
        raise ConnectionError((host, port), reason)

    def _on_message(self, args):
        msg = Message.initialize(args)
        if msg is None:
            return

        try:
            if msg.id == message.RPC_CHUNK:
                self._subscribers[msg.session].callback(msgpack.unpackb(msg.data))
            elif msg.id == message.RPC_CHOKE:
                future = self._subscribers.pop(msg.session, None)
                if future is not None:
                    future.close()
            elif msg.id == message.RPC_ERROR:
                self._subscribers[msg.session].error(ServiceError(self.name, msg.message, msg.code))
        except Exception as err:
            log.warning('"_on_message" method has caught an error - %s', err)
            raise err

    def _invoke(self, methodId):
        def wrapper(*args, **kwargs):
            if not self.isConnected():
                raise IllegalStateError('service "{0}" is not connected'.format(self.name))

            future = Future()
            timeout = kwargs.get('timeout', None)
            if timeout is not None:
                fd = self._ioLoop.add_timeout(time() + timeout, lambda: future.error(TimeoutError(timeout)))

                def timeoutRemover(func):
                    def wrapper(*args, **kwargs):
                        self._ioLoop.remove_timeout(fd)
                        return func(*args, **kwargs)
                    return wrapper
                future.close = timeoutRemover(future.close)
            self._session += 1
            self._writableStream.write([methodId, self._session, args])
            self._subscribers[self._session] = future
            return Chain([lambda: future])
        return wrapper

    def perform_sync(self, method, *args, **kwargs):
        """Performs synchronous method invocation.

        Note: Left for backward compatibility.
        """
        if not self.isConnected():
            raise IllegalStateError('service "{0}" is not connected'.format(self.name))

        if method not in self.api:
            raise ValueError('service "{0}" has no method named "{1}"'.format(self.name, method))

        timeout = kwargs.get('timeout', None)
        if timeout is not None and timeout <= 0:
            raise ValueError('timeout must be positive number')

        with scope.socket.timeout(self._pipe.sock, timeout) as sock:
            self._session += 1
            sock.send(msgpack.dumps([self.api[method], self._session, args]))
            unpacker = msgpack.Unpacker()
            error = None
            while True:
                data = sock.recv(4096)
                unpacker.feed(data)
                for chunk in unpacker:
                    msg = Message.initialize(chunk)
                    if msg is None:
                        continue
                    if msg.id == message.RPC_CHUNK:
                        yield msgpack.loads(msg.data)
                    elif msg.id == message.RPC_CHOKE:
                        raise error or StopIteration
                    elif msg.id == message.RPC_ERROR:
                        error = ServiceError(self.name, msg.message, msg.code)


class Locator(AbstractService):
    RESOLVE_METHOD_ID = 0

    def __init__(self, isBlocking):
        super(Locator, self).__init__('locator', isBlocking)
        self.api = {
            'resolve': self.RESOLVE_METHOD_ID
        }

    def connect(self, host, port, timeout):
        return self._connectToEndpoint(host, port, timeout)

    def resolve(self, name, timeout=None):
        if self.isBlocking:
            (endpoint, session, api), = [chunk for chunk in self.perform_sync('resolve', name, timeout=timeout)]
            return endpoint, session, api
        else:
            return self._invoke(self.RESOLVE_METHOD_ID)(name, timeout=timeout)


class Service(AbstractService):
    def __init__(self, name, connectNow=True, host=LOCATOR_DEFAULT_HOST, port=LOCATOR_DEFAULT_PORT):
        super(Service, self).__init__(name, connectNow)

        if not connectNow and any([host != LOCATOR_DEFAULT_HOST, port != LOCATOR_DEFAULT_PORT]):
            raise ValueError('you should not specify locator address in __init__ while performing non-blocking connect')

        self.locator = Locator(connectNow)
        self.connect = strategy.init(self.connect, connectNow)
        if connectNow:
            self.connect(host, port)

    def connect(self, host=LOCATOR_DEFAULT_HOST, port=LOCATOR_DEFAULT_PORT, timeout=None):
        """Connect to the service through locator.

        :param host: locator host
        :param port: locator port
        :param timeout: timeout
        """
        with cumulative(timeout) as timeLeft:
            yield self.locator.connect(host, port, timeout=timeLeft())
            endpoint, session, api = yield self.locator.resolve(self.name, timeout=timeLeft())
            self.api = dict((methodName, methodId) for methodId, methodName in api.items())
            yield self._connectToEndpoint(*endpoint, timeout=timeLeft())
            for methodId, methodName in api.items():
                setattr(self, methodName, self._invoke(methodId))