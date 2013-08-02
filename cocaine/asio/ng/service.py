from contextlib import contextmanager
import logging
import msgpack
import socket
from time import time

from cocaine.asio.ng import ConnectionResolveError, ConnectionError, ConnectionTimeoutError, IllegalStateError
from cocaine.asio.ng.pipe import Pipe
from cocaine.futures.chain import Chain
from cocaine.asio import message
from cocaine.asio.message import Message
from cocaine.exceptions import ServiceError, TimeoutError
from cocaine.asio.stream import Decoder, WritableStream, ReadableStream
from cocaine.futures import chain, Future

__author__ = 'Evgeny Safronov <division494@gmail.com>'


log = logging.getLogger(__name__)


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


class watcher(object):
    class socket(object):
        @classmethod
        @contextmanager
        def blocking(cls, sock):
            try:
                sock.setblocking(True)
                yield sock
            finally:
                sock.setblocking(False)


RESOLVE_METHOD_ID = 0


class AbstractService(object):
    def __init__(self, name, isBlocking):
        self.name = name
        self.isBlocking = isBlocking
        self._connect = strategy.init(self._connect, isBlocking)

        self._pipe = None
        self._ioLoop = None
        self._writableStream = None
        self._readableStream = None

        self.decoder = Decoder()
        self.decoder.bind(self._on_message)

        self._subscribers = {}
        self._session = 0

    def isConnected(self):
        return self._pipe is not None and self._pipe.isConnected()

    def _connect(self, host, port, timeout=None):
        if self.isConnected():
            raise IllegalStateError('service "{0}" is already connected'.format(self.name))

        addressInfoList = socket.getaddrinfo(host, port, 0, socket.SOCK_STREAM)
        if not addressInfoList:
            raise ConnectionResolveError(host, port)

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
            raise ConnectionTimeoutError(host, port, timeout)

        reason = 'multiple connection errors: ' + ', '.join(err.message for err in errors)
        raise ConnectionError(host, port, reason)

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
                raise ServiceError(self.name, 'service is disconnected', -200)

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


class Locator(AbstractService):
    def __init__(self, isBlocking):
        super(Locator, self).__init__('locator', isBlocking)

    def connect(self, host, port, timeout=None):
        return self._connect(host, port, timeout)

    def resolve(self, name, timeout=None):
        if self.isBlocking:
            return self._blockingResolve(name, timeout)
        else:
            return self._nonBlockingResolve(name, timeout)

    def _blockingResolve(self, name, timeout):
        try:
            self._pipe.sock.settimeout(timeout)
            self._session += 1
            self._writableStream.write([RESOLVE_METHOD_ID, self._session, [name]])
            unpacker = msgpack.Unpacker()
            messages = []
            while True:
                response = self._pipe.sock.recv(4096)
                unpacker.feed(response)
                for msg in unpacker:
                    msg = Message.initialize(msg)
                    messages.append(msg)
                if messages and messages[-1].id == message.RPC_CHOKE:
                    break

            assert len(messages) == 2, 'protocol is corrupted! Locator must return exactly 2 chunks'
            chunk, choke = messages
            if chunk.id == message.RPC_ERROR:
                raise Exception(chunk.message)
            return msgpack.loads(chunk.data)
        finally:
            self._pipe.sock.setblocking(False)

    def _nonBlockingResolve(self, name, timeout):
        return self._invoke(RESOLVE_METHOD_ID)(name, timeout=timeout)


class Service(AbstractService):
    def __init__(self, name, isBlocking=True):
        super(Service, self).__init__(name, isBlocking)
        self.locator = Locator(isBlocking)
        self.connect = strategy.init(self.connect, isBlocking)
        self.api = {}
        if isBlocking:
            self.connect()

    def connect(self, host='127.0.0.1', port=10053, timeout=None):
        """Connect to the service through locator.

        :param host: locator host
        :param port: locator port
        :param timeout: timeout
        """
        with cumulative(timeout) as timeLeft:
            yield self.locator.connect(host, port, timeout=timeLeft())
            endpoint, session, api = yield self.locator.resolve(self.name, timeout=timeLeft())
            self.api = dict((methodName, methodId) for methodId, methodName in api.items())
            yield self._connect(*endpoint, timeout=timeLeft())
            for methodId, methodName in api.items():
                setattr(self, methodName, self._invoke(methodId))

    def perform_sync(self, method, *args, **kwargs):
        """Performs synchronous method invocation.

        Note: Left for backward compatibility.
        """
        if not self.isConnected():
            raise IllegalStateError('service is not connected')

        if method not in self.api:
            raise ValueError('service "{0}" has no method named "{1}"'.format(self.name, method))

        with watcher.socket.blocking(self._pipe.sock) as sock:
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
                        error = Exception(msg.message)
