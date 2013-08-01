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


class AbstractService(object):
    def __init__(self, name):
        self.name = name
        self._pipe = None
        self._ioLoop = None
        self._writableStream = None
        self._readableStream = None

        self.decoder = Decoder()
        self.decoder.bind(self._on_message)

        self._subscribers = {}
        self._session = 0

    @chain.source
    def _connect(self, endpoint):
        addressInfoList = filter(lambda (f, t, p, c, a): t == socket.SOCK_STREAM, socket.getaddrinfo(*endpoint))
        print(addressInfoList)
        for family, socktype, proto, canonname, address in addressInfoList:
            sock = socket.socket(family=family, type=socktype, proto=proto)
            try:
                print(family, socktype, proto, canonname, address)
                self._pipe = Pipe(sock)
                yield self._pipe.connect(address, timeout=0.1)
            except ConnectionError as err:
                print('base, error', err)
            else:
                self._ioLoop = self._pipe._ioLoop
                self._writableStream = WritableStream(self._ioLoop, self._pipe)
                self._readableStream = ReadableStream(self._ioLoop, self._pipe)
                self._ioLoop.bind_on_fd(self._pipe.fileno())
                self._readableStream.bind(self.decoder.decode)
                break
        yield 'Successfully connected to the {0}'.format(endpoint)

    def _on_message(self, args):
        print('!Chunk', args)
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


class Locator(AbstractService):
    def __init__(self):
        super(Locator, self).__init__('locator')

    @chain.source
    def connect(self, endpoint):
        yield self._connect(endpoint)

    def resolve(self, name):
        future = Future()
        self._session += 1
        self._writableStream.write([0, 1, [name]])
        self._subscribers[self._session] = future
        return Chain([lambda: future])


class Service(AbstractService):
    def __init__(self, name):
        super(Service, self).__init__(name)
        self.locator = Locator()

    @chain.source
    def connect(self, locatorEndpoint=('127.0.0.1', 10053)):
        try:
            print('Before locator connect')
            yield self.locator.connect(endpoint=locatorEndpoint)
            print('Before resolve')
            endpoint, session, api = yield self.locator.resolve(self.name)
            print('After resolve:', endpoint, api)
        except Exception as err:
            print('err', err)
