import datetime

from cocaine.exceptions import ChokeEvent
from cocaine.concurrent import Deferred


__author__ = 'Evgeny Safronov <division494@gmail.com>'


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