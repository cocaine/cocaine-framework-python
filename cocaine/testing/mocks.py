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


class _MessageMock(object):
    def __init__(self, id_):
        self.id = id_

    def pack(self, session):
        return msgpack.dumps([self.id, session, self._data()])

    def _data(self):
        return []

    def __str__(self):
        return '{0}({1})'.format(self.__class__.__name__, self._data())


class Chunk(_MessageMock):
    def __init__(self, data):
        super(Chunk, self).__init__(RPC.CHUNK)
        self.data = data

    def _data(self):
        return [msgpack.dumps(self.data)]

    def __str__(self):
        return '{0}({1})'.format(self.__class__.__name__, self.data)


class Error(_MessageMock):
    def __init__(self, errno, reason):
        super(Error, self).__init__(RPC.ERROR)
        self.errno = errno
        self.reason = reason

    def _data(self):
        return [self.errno, self.reason]


class Choke(_MessageMock):
    def __init__(self):
        super(Choke, self).__init__(RPC.CHOKE)


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

    def invoke(self, event, *args):
        class _Invoker(object):
            def __init__(self, callbacks):
                self._callbacks = callbacks

            def answer(self, sequence):
                self._callbacks[('invoke', event, args)] = sequence

        return _Invoker(self.callbacks)

    def __getitem__(self, item):
        return self.callbacks[item]

    def __contains__(self, item):
        return item in self.callbacks


class Connection(object):
    def __init__(self, stream, hook):
        self._stream = stream
        self._hook = hook
        self._closed = True
        self._unpacker = msgpack.Unpacker()

        self._hook['connected']()
        self._stream.read_until_close(self._on_closed, self._on_chunk)

    def closed(self):
        return self._closed

    def _on_closed(self, data):
        assert 0 == len(data)
        log.debug('stream is closed')
        self._hook['disconnected']()

    def _on_chunk(self, data):
        log.debug('received raw data: %s', data)
        self._unpacker.feed(data)
        for chunk in self._unpacker:
            log.debug('received message: %s', chunk)
            id_, session, data = chunk
            if self._closed:
                if ('invoke', id_, tuple(data)) in self._hook:
                    sequence = self._hook['invoke', id_, tuple(data)]
                    self._send_response(session, sequence)
            else:
                if ('push', id_, tuple(data)) in self._hook:
                    sequence = self._hook['push', id_, tuple(data)]
                    self._send_response(session, sequence)

    def _send_response(self, session, responses):
        assert hasattr(responses, '__iter__'), 'responses object must be iterable'
        log.debug('iterating over responses: %s', responses)
        for response in responses:
            log.debug('sending: %s', response)
            self._stream.write(response.pack(session))
            if response.id == RPC.CHOKE:
                self._closed = True
                self._stream.close()


class AppServerMock(TCPServer):
    def __init__(self, name, port, hook):
        super(AppServerMock, self).__init__()
        self._name = name
        self._hook = hook
        self._connections = []
        self.listen(port)

    def handle_stream(self, stream, address):
        log.debug('connection accepted for "%s" from %s', self._name, address)
        self._connections.append(Connection(stream, self._hook))


class RuntimeMock(object):
    def __init__(self, port=10053):
        self._services = {}
        self._hooks = collections.defaultdict(Hook)
        self._servers = []

        self.register('locator', port, 1, {})

    def register(self, name, port, version, api):
        assert name not in self._services, 'service already registered'
        log.debug('registering "%s" at (%s, %d)', name, 'localhost', port)

        self._services[name] = port
        self.when('locator').invoke(0, name).answer([
            Chunk([['localhost', port], version, api]),
            Choke()
        ])

    def when(self, name):
        return self._hooks[name]

    def start(self):
        for name, port in self._services.iteritems():
            server = AppServerMock(name, port, self._hooks[name])
            self._servers.append(server)

    def stop(self):
        for server in self._servers:
            server.stop()