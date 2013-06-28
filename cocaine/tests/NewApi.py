import time
from tornado.ioloop import IOLoop
from tornado.testing import AsyncTestCase
from cocaine.futures.chain import ChainFactory
from cocaine.futures import Future

__author__ = 'esafronov'

import unittest


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
            return self.callback(chunk)

        def choke(self):
            self.errorback(StopIteration('Choke'))


class ServiceMock(object):
    def __init__(self, chunks=None, T=ChainFactory, ioLoop=IOLoop.instance()):
        if not chunks:
            chunks = [None]
        self.chunks = chunks
        self.ioLoop = ioLoop
        self.T = T

    def execute(self):
        return self.T([lambda: FutureTestMock(self.ioLoop, self.chunks)], ioLoop=self.ioLoop)


def multiThenStopAssert(obj, expected):
    def wrapper(func):
        class decorator(object):
            def __init__(self):
                self.expected = expected
                self.pos = 0

            def __call__(self, r):
                try:
                    func(self.expected[self.pos], r)
                    self.pos += 1
                    if self.pos == len(self.expected):
                        obj.stop()
                except StopIteration:
                    obj.stop()
        return decorator()
    return wrapper

# =====================================================================================================================


class FutureResult(object):
    def __init__(self, result):
        self.result = result

    def get(self):
        if isinstance(self.result, Exception):
            raise self.result
        else:
            return self.result


class FutureMock(Future):
    def __init__(self, result, ioLoop=IOLoop.instance()):
        super(FutureMock, self).__init__()
        self.result = result
        self.ioLoop = ioLoop

    def bind(self, callback, errorback=None, on_done=None):
        try:
            self.ioLoop.add_callback(callback, self.result)
        except Exception as err:
            self.ioLoop.add_callback(errorback, err)


class ChainItem(object):
    def __init__(self, func, ioLoop=IOLoop.instance()):
        self.func = func
        self.ioLoop = ioLoop
        self.nextChainItem = None

    def execute(self, *args, **kwargs):
        try:
            print(2)
            future = self.func(*args, **kwargs)
            if isinstance(future, Future):
                pass
            else:
                future = FutureMock(future, ioLoop=self.ioLoop)
            print(3, future)
            future.bind(self.callback, self.errorback)
        except Exception as err:
            self.errorback(err)

    def callback(self, chunk):
        print('cb', chunk)
        futureResult = FutureResult(chunk)
        if self.nextChainItem:
            self.ioLoop.add_callback(self.nextChainItem.execute, futureResult)
            #self.nextChainItem.execute(futureResult)

    def errorback(self, error):
        print('error', error)
        self.callback(error)


class Chain(object):
    def __init__(self, functions=None, ioLoop=IOLoop.instance()):
        if not functions:
            functions = []
        self.ioLoop = ioLoop
        self.chainItems = []
        for func in functions:
            self.then(func)

    def then(self, func):
        chainItem = ChainItem(func, self.ioLoop)
        if len(self.chainItems) > 0:
            self.chainItems[-1].nextChainItem = chainItem

        if len(self.chainItems) == 0:
            print(1)
            self.ioLoop.add_callback(chainItem.execute)
        self.chainItems.append(chainItem)
        return self


class NewApiTestCase(AsyncTestCase):
    def test_SingleChunk_SingleThen(self):
        @multiThenStopAssert(self, [1])
        def check(expected, r):
            self.assertEqual(r.get(), expected)
        f = ServiceMock(chunks=[1], T=Chain, ioLoop=self.io_loop).execute()
        f.then(check)
        self.wait(timeout=0.5)

    def test_MultipleChunks_SingleThen(self):
        @multiThenStopAssert(self, [1, 2, 3])
        def check(expected, r):
            self.assertEqual(r.get(), expected)
        f = ServiceMock(chunks=[1, 2, 3], T=Chain, ioLoop=self.io_loop).execute()
        f.then(check)
        self.wait(timeout=0.5)

    def test_SingleChunk_MultipleThen(self):
        @multiThenStopAssert(self, [1])
        def check(expected, r):
            self.assertEqual(r.get(), expected)
        f = ServiceMock(chunks=[1], T=Chain, ioLoop=self.io_loop).execute()
        f.then(lambda r: r.get()).then(check)
        self.wait(timeout=0.5)

    def test_MultipleChunks_MultipleThen(self):
        @multiThenStopAssert(self, [1, 2, 3])
        def check(expected, r):
            self.assertEqual(r.get(), expected)
        f = ServiceMock(chunks=[1, 2, 3], T=Chain, ioLoop=self.io_loop).execute()
        f.then(lambda r: r.get()).then(check)
        self.wait(timeout=0.5)

    def test_SingleChunk_SingleThen_SyncResult(self):
        @multiThenStopAssert(self, [1])
        def check(expected, r):
            self.assertEqual(r.get(), expected)
        f = Chain([lambda: 1], ioLoop=self.io_loop)
        f.then(lambda r: r.get()).then(check)
        self.wait(timeout=0.5)

if __name__ == '__main__':
    unittest.main()
