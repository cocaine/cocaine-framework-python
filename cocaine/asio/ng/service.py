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


class ConnectStrategy:
    def connect(self, service, endpoint):
        raise NotImplementedError()


class SynchronousConnectStrategy(ConnectStrategy):
    def connect(self, service, endpoint):
        pass


class AsynchronousConnectStrategy(ConnectStrategy):
    @chain.source
    def connect(self, service, endpoint):
        addressInfoList = filter(lambda (f, t, p, c, a): t == socket.SOCK_STREAM, socket.getaddrinfo(*endpoint))
        print(addressInfoList)
        for family, socktype, proto, canonname, address in addressInfoList:
            sock = socket.socket(family=family, type=socktype, proto=proto)
            try:
                print(family, socktype, proto, canonname, address)
                service._pipe = Pipe(sock)
                yield service._pipe.connect(address, timeout=0.1)
            except ConnectionError as err:
                print('base, error', err)
            else:
                service._ioLoop = service._pipe._ioLoop
                service._writableStream = WritableStream(service._ioLoop, service._pipe)
                service._readableStream = ReadableStream(service._ioLoop, service._pipe)
                service._ioLoop.bind_on_fd(service._pipe.fileno())
                service._readableStream.bind(service.decoder.decode)
                break
        yield 'Successfully connected to the {0}'.format(endpoint)


class AbstractService(object):
    def __init__(self, name, ConnectionStrategy):
        self.name = name
        self.connectionStrategy = ConnectionStrategy()

        self._pipe = None
        self._ioLoop = None
        self._writableStream = None
        self._readableStream = None

        self.decoder = Decoder()
        self.decoder.bind(self._on_message)

        self._subscribers = {}
        self._session = 0

    def _connect(self, endpoint):
        return self.connectionStrategy.connect(self, endpoint)

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
            print(methodId, self._session, args)
            self._writableStream.write([methodId, self._session, args])
            self._subscribers[self._session] = future
            return Chain([lambda: future])
        return wrapper

    def isConnected(self):
        return self._pipe is not None and self._pipe.isConnected()


class Locator(AbstractService):
    def __init__(self, ConnectionStrategy):
        super(Locator, self).__init__('locator', ConnectionStrategy)

    @chain.source
    def connect(self, endpoint):
        yield self._connect(endpoint)

    def resolve(self, name):
        RESOLVE_METHOD_ID = 0
        return self.closure(RESOLVE_METHOD_ID)(name)


class Service(AbstractService):
    def __init__(self, name, ConnectionStrategy=AsynchronousConnectStrategy):
        super(Service, self).__init__(name, ConnectionStrategy)
        self.locator = Locator(ConnectionStrategy)

    @chain.source
    def connect(self, locatorEndpoint=('127.0.0.1', 10053)):
        try:
            yield self.locator.connect(endpoint=locatorEndpoint)
            endpoint, session, api = yield self.locator.resolve(self.name)
            print(endpoint, session, api)
            yield super(Service, self)._connect(endpoint)
            for methodId, methodName in api.items():
                setattr(self, methodName, self.closure(methodId))
        except Exception as err:
            print('err', err)