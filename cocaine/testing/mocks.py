import time
from tornado.ioloop import IOLoop
from cocaine.exceptions import ChokeEvent
from cocaine.futures import Future
from cocaine.futures.chain import ChainFactory
import logging

__author__ = 'Evgeny Safronov <division494@gmail.com>'


log = logging.getLogger(__name__)


class CallableMock(object):
    def __init__(self, mock):
        self.mock = mock

    def __call__(self, *args, **kwargs):
        return self.mock.__call__(*args, **kwargs)

    def __getattr__(self, methodName):
        return self.mock.__getattr__(methodName)


class FutureTestMock(Future):
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
                self.ioLoop.add_timeout(time.time() + (pos + 1) * self.interval, self.invoke)
            self.ioLoop.add_timeout(time.time() + (len(self.chunks) + 1) * self.interval, self.choke)

        def invoke(self):
            chunk = self.chunks[self.currentChunkId]
            self.currentChunkId += 1
            if isinstance(chunk, Exception):
                self.errorback(chunk)
            else:
                self.callback(chunk)

        def choke(self):
            self.errorback(ChokeEvent('Choke'))


class ServiceMock(object):
    def __init__(self, chunks=None, T=ChainFactory, ioLoop=None, interval=0.01):
        if not chunks:
            chunks = [None]
        self.chunks = chunks
        self.ioLoop = ioLoop or IOLoop.instance()
        self.T = T
        self.interval = interval

    def execute(self):
        return self.T([lambda: FutureTestMock(self.ioLoop, self.chunks, self.interval)], ioLoop=self.ioLoop)


def checker(conditions, self):
    def check(result):
        try:
            condition = conditions.pop(0)
            log.debug('>>>>>>>>>>>>>>>>>>>>>>>>>> Test check. Actual: {0}'.format(repr(result.result)))
            condition(result)
        except AssertionError as err:
            log.debug('>>>>>>>>>>>>>>>>>>>>>>>>>> Test check failed. Actual - {0}. Error - {1}', result.result, err)
            exit(1)
        finally:
            if not conditions:
                self.stop()
    return check