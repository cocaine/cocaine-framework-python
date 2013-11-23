import collections
import datetime
import functools
import logging
import sys
import msgpack

from tornado.tcpserver import TCPServer

from cocaine.concurrent import Deferred
from cocaine.protocol import ChokeEvent
from cocaine.protocol.message import Message, RPC


__author__ = 'Evgeny Safronov <division494@gmail.com>'


log = logging.getLogger(__name__)
h = logging.StreamHandler(stream=sys.stdout)
log.addHandler(h)
log.setLevel(logging.DEBUG)
log.propagate = False


class CallableMock(object):
    def __init__(self, mock):
        self.mock = mock

    def __call__(self, *args, **kwargs):
        return self.mock.__call__(*args, **kwargs)

    def __getattr__(self, methodName):
        return self.mock.__getattr__(methodName)


class FutureTestMock(Deferred):
    def __init__(self, ioLoop, chunks=None, interval=0.01):
        super(FutureTestMock, self).__init__()
        self.ioLoop = ioLoop
        self.chunks = chunks
        self.interval = interval
        self.currentChunkId = 0

    def bind(self, callback, errorback=None, on_done=None):
        self.callback = callback
        self.errorback = errorback
        self.doneback = on_done
        self.start()

    def start(self):
        for pos, value in enumerate(self.chunks):
            delta = datetime.timedelta(seconds=(pos + 1) * self.interval)
            self.ioLoop.add_timeout(delta, self.invoke)

        delta = datetime.timedelta(seconds=(len(self.chunks) + 1) * self.interval)
        self.ioLoop.add_timeout(delta, self.choke)

    def invoke(self):
        chunk = self.chunks[self.currentChunkId]
        self.currentChunkId += 1
        if isinstance(chunk, Exception):
            self.errorback(chunk)
        else:
            self.callback(chunk)

    def choke(self):
        self.errorback(ChokeEvent())


class RuntimeMockError(object):
    def __init__(self, errno, reason):
        self.errno = errno
        self.reason = reason


class Hook(object):
    def __init__(self):
        self.callbacks = {
            'connected': lambda: None,
            'disconnected': lambda: None
        }

    def connected(self, action):
        self.callbacks['connected'] = action

    def disconnected(self, action):
        self.callbacks['disconnected'] = action

    def message(self, request, response, action=lambda: None):
        self.callbacks[('message', msgpack.dumps(request))] = (response, action)

    def __getitem__(self, item):
        return self.callbacks[item]


class AppServerMock(TCPServer):
    def __init__(self, name, port, hook):
        super(AppServerMock, self).__init__()
        self._name = name
        self._hook = hook
        self._unpacker = msgpack.Unpacker()
        self.listen(port)

    def handle_stream(self, stream, address):
        log.debug('connection accepted for "%s" from %s', self._name, address)
        stream.read_until_close(self._on_closed, functools.partial(self._on_chunk, stream))
        self._hook['connected']()

    def _on_closed(self, data):
        assert 0 == len(data)
        log.debug('stream for "%s" is closed', self._name)
        self._hook['disconnected']()

    def _on_chunk(self, stream, data):
        log.debug('received raw data: %s', data)
        self._unpacker.feed(data)
        for chunk in self._unpacker:
            log.debug('received message: %s', chunk)
            id_, session, data = chunk
            if ('message', msgpack.dumps(chunk)) in self._hook.callbacks:
                response, action = self._hook[('message', msgpack.dumps(chunk))]
                action()
                self._send_response(stream, session, response)

    def _send_response(self, stream, session, responses):
        assert hasattr(responses, '__iter__'), 'responses object must be iterable'
        log.debug('iterating over response: %s', responses)
        for response in responses:
            log.debug('sending: %s', response)
            if isinstance(response, RuntimeMockError):
                msg = Message(RPC.ERROR, session, response.errno, response.reason)
            else:
                msg = Message(RPC.CHUNK, session, msgpack.dumps(response))
            stream.write(msg.pack())
        stream.write(Message(RPC.CHOKE, session).pack())
        stream.close()


class RuntimeMock(object):
    def __init__(self, port=10053):
        self._services = {}
        self._hooks = collections.defaultdict(Hook)
        self._servers = []

        self.register('locator', 0, port, 1, {})

    def register(self, name, session, port, version, api):
        assert name not in self._services, 'service already registered'
        log.debug('registering "%s" at (%s, %d)', name, 'localhost', port)

        self._services[name] = port
        self.when('locator').message([0, session, [name]],
                                     [[['localhost', port], version, api]])

    def when(self, name):
        return self._hooks[name]

    def start(self):
        for name, port in self._services.iteritems():
            server = AppServerMock(name, port, self._hooks[name])
            self._servers.append(server)

    def stop(self):
        for server in self._servers:
            server.stop()