import datetime
import time
import sys
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
            TIME_FORMAT = '%H:%M:%S.%f'
            now = datetime.datetime.now()
            for pos, value in enumerate(self.chunks):
                delta = datetime.timedelta(seconds=(pos + 1) * self.interval)
                self.ioLoop.add_timeout(delta, self.invoke)
                log.debug('Chunk will come in {0}'.format((now + delta).strftime(TIME_FORMAT)))

            delta = datetime.timedelta(seconds=len(self.chunks) * self.interval + 0.01)
            self.ioLoop.add_timeout(delta, self.choke)
            log.debug('Choke will come in {0}'.format((now + delta).strftime(TIME_FORMAT)))

        def invoke(self):
            chunk = self.chunks[self.currentChunkId]
            self.currentChunkId += 1
            if isinstance(chunk, Exception):
                self.errorback(chunk)
            else:
                self.callback(chunk)

        def choke(self):
            self.errorback(ChokeEvent())


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
            log.debug('>>> Check Condition. Actual: {0}'.format(repr(result.result)))
            condition(result)
        except AssertionError as err:
            log.debug('>>> Assert Error. Actual - {0}. Error - {1}', result.result, err)
            sys.exit(1)
        except Exception as err:
            log.debug('>>>> Unknown Error. Actual - {0}. Error - {1}', result.result, err)
            sys.exit(2)
        finally:
            if not conditions:
                self.stop()
    return check