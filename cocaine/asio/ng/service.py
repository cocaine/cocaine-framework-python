import logging
import msgpack
import socket
from time import time

from cocaine.asio.ng import ConnectionResolveError, ConnectionError, ConnectionTimeoutError
from cocaine.asio.ng.pipe import Pipe
from cocaine.futures.chain import Chain
from cocaine.asio import message
from cocaine.asio.message import Message
from cocaine.exceptions import ServiceError
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


RESOLVE_METHOD_ID = 0


class AbstractService(object):
    def __init__(self, name, isBlocking):
        self.name = name
        self.isBlocking = isBlocking

        self._pipe = None
        self._ioLoop = None
        self._writableStream = None
        self._readableStream = None

        self.decoder = Decoder()
        self.decoder.bind(self._on_message)

        self._subscribers = {}
        self._session = 0

        self._connect = strategy.init(self._connect, isBlocking)

    def isConnected(self):
        return self._pipe is not None and self._pipe.isConnected()

    def _connect(self, host, port, timeout=None):
        addressInfoList = socket.getaddrinfo(host, port, 0, socket.SOCK_STREAM)
        if not addressInfoList:
            raise ConnectionResolveError(host, port)
        print(addressInfoList)

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

        if time() - start > timeout:
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

    def _closure(self, methodId):
        def wrapper(*args):
            if not self.isConnected():
                raise ServiceError(self.name, 'service is disconnected', -200)
            future = Future()
            self._session += 1
            self._writableStream.write([methodId, self._session, args])
            self._subscribers[self._session] = future
            return Chain([lambda: future])
        return wrapper


class Locator(AbstractService):
    def __init__(self, isBlocking):
        super(Locator, self).__init__('locator', isBlocking)

    def connect(self, host, port):
        return self._connect(host, port)

    def resolve(self, name, timeout=None):
        if self.isBlocking:
            return self._blockingResolve(name, timeout)
        else:
            return self._nonBlockingResolve(name, timeout)

    def _blockingResolve(self, name, timeout):
        try:
            self._pipe.sock.settimeout(timeout)
            self._writableStream.write([0, 1, [name]])
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
        return self._closure(RESOLVE_METHOD_ID)(name)


class Service(AbstractService):
    def __init__(self, name, isBlocking=False):
        super(Service, self).__init__(name, isBlocking)
        self.locator = Locator(isBlocking)
        self.connect = strategy.init(self.connect, isBlocking)

    def connect(self, host='127.0.0.1', port=10053):
        yield self.locator.connect(host, port)
        endpoint, session, api = yield self.locator.resolve(self.name)
        yield self._connect(*endpoint)
        for methodId, methodName in api.items():
            setattr(self, methodName, self._closure(methodId))