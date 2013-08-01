import msgpack
import socket
from cocaine.asio.ng.pipe import Pipe
from cocaine.futures.chain import Chain
from cocaine.asio import message
from cocaine.asio.message import Message
from cocaine.exceptions import ConnectionError, ServiceError
from cocaine.asio.stream import Decoder, WritableStream, ReadableStream
from cocaine.futures import chain, Future

__author__ = 'Evgeny Safronov <division494@gmail.com>'


RESOLVE_METHOD_ID = 0


class AbstractService(object):
    DEFAULT_TIMEOUT = 5.0

    def __init__(self, name, blocking):
        self.name = name
        self.blocking = blocking

        self._pipe = None
        self._ioLoop = None
        self._writableStream = None
        self._readableStream = None

        self.decoder = Decoder()
        self.decoder.bind(self._on_message)

        self._subscribers = {}
        self._session = 0

    def _connect(self, endpoint):
        if self.blocking:
            return self._connectSynchronously(endpoint)
        else:
            return self._connectAsynchronously(endpoint)

    @chain.source
    def _connectAsynchronously(self, endpoint):
        addressInfoList = filter(lambda (f, t, p, c, a): t == socket.SOCK_STREAM, socket.getaddrinfo(*endpoint))
        for family, socktype, proto, canonname, address in addressInfoList:
            sock = socket.socket(family=family, type=socktype, proto=proto)
            try:
                self._pipe = Pipe(sock)
                yield self._pipe.connect(address, timeout=1)
            except ConnectionError:
                pass
            else:
                self._ioLoop = self._pipe._ioLoop
                self._writableStream = WritableStream(self._ioLoop, self._pipe)
                self._readableStream = ReadableStream(self._ioLoop, self._pipe)
                self._ioLoop.bind_on_fd(self._pipe.fileno())
                self._readableStream.bind(self.decoder.decode)
                break

    def _connectSynchronously(self, endpoint):
        addressInfoList = filter(lambda (f, t, p, c, a): t == socket.SOCK_STREAM, socket.getaddrinfo(*endpoint))
        for family, socktype, proto, canonname, address in addressInfoList:
            sock = socket.socket(family=family, type=socktype, proto=proto)
            try:
                self._pipe = Pipe(sock)
                self._pipe.connect(address, timeout=1, blocking=True)
            except socket.error:
                pass
            else:
                self._ioLoop = self._pipe._ioLoop
                self._writableStream = WritableStream(self._ioLoop, self._pipe)
                self._readableStream = ReadableStream(self._ioLoop, self._pipe)
                self._ioLoop.bind_on_fd(self._pipe.fileno())
                self._readableStream.bind(self.decoder.decode)
                break

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
            print "Exception in _on_message: %s" % str(err)
            raise err

    def closure(self, methodId):
        def wrapper(*args):
            if not self.isConnected():
                raise ServiceError(self.name, 'service is disconnected', -200)
            future = Future()
            self._session += 1
            self._writableStream.write([methodId, self._session, args])
            self._subscribers[self._session] = future
            return Chain([lambda: future])
        return wrapper

    def isConnected(self):
        return self._pipe is not None and self._pipe.isConnected()


class Locator(AbstractService):
    def __init__(self, blocking):
        super(Locator, self).__init__('locator', blocking)

    def connect(self, endpoint):
        return self._connect(endpoint)

    def resolve(self, name):
        if not self.blocking:
            return self.closure(RESOLVE_METHOD_ID)(name)
        else:
            try:
                self._pipe.sock.settimeout(5.0)
                self._writableStream.write([0, 1, [name]])
                unpacker = msgpack.Unpacker()
                messages = []
                while True:
                    response = self._pipe.sock.recv(4)
                    unpacker.feed(response)
                    for msg in unpacker:
                        msg = Message.initialize(msg)
                        messages.append(msg)
                    if messages and messages[-1].id == message.RPC_CHOKE:
                        break
                assert len(messages) == 2
                chunk, choke = messages
                if chunk.id == message.RPC_ERROR:
                    raise Exception(chunk.message)
                return msgpack.loads(chunk.data)
            finally:
                self._pipe.sock.setblocking(False)


class Service(AbstractService):
    def __init__(self, name, blocking=False):
        super(Service, self).__init__(name, blocking)
        self.locator = Locator(blocking)

    def connect(self, locatorEndpoint=('127.0.0.1', 10053)):
        if self.blocking:
            return self._resolveAndConnectSynchronously(locatorEndpoint)
        else:
            return self._resolveAndConnectAsynchronously(locatorEndpoint)

    @chain.source
    def _resolveAndConnectAsynchronously(self, locatorEndpoint):
        yield self.locator.connect(endpoint=locatorEndpoint)
        endpoint, session, api = yield self.locator.resolve(self.name)
        yield self._connect(endpoint)
        for methodId, methodName in api.items():
            setattr(self, methodName, self.closure(methodId))

    def _resolveAndConnectSynchronously(self, locatorEndpoint):
        self.locator.connect(locatorEndpoint)
        endpoint, session, api = self.locator.resolve(self.name)
        self._connect(endpoint)
        for methodId, methodName in api.items():
            setattr(self, methodName, self.closure(methodId))
