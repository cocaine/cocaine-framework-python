import time
import sys
import types
from cocaine.services import Service
from tornado.ioloop import IOLoop
from tornado.testing import AsyncTestCase
from cocaine.futures.chain import ChainFactory
from cocaine.futures import Future

__author__ = 'esafronov'

import unittest


class ChokeEvent(Exception):
    pass


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
            self.errorback(ChokeEvent('Choke'))


class ServiceMock(object):
    def __init__(self, chunks=None, T=ChainFactory, ioLoop=IOLoop.instance(), interval=0.01):
        if not chunks:
            chunks = [None]
        self.chunks = chunks
        self.ioLoop = ioLoop
        self.T = T
        self.interval = interval

    def execute(self):
        return self.T([lambda: FutureTestMock(self.ioLoop, self.chunks, self.interval)], ioLoop=self.ioLoop)


def checker(conditions, self):
    def check(result):
        try:
            condition = conditions.pop(0)
            print('>>>>>>>>>>>>>>>>>>>>>>>>>> {0}'.format(result.result))
            condition(result)
        except AssertionError as err:
            print('>>>>>>>>>>>>>>>>>>>>>>>>>> {0}'.format(repr(err)))
            exit(1)
        finally:
            if not conditions:
                self.stop()
    return check

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


class FutureCallableMock(Future):
    def bind(self, callback, errorback=None, on_done=None):
        self.callback = callback
        self.errorback = errorback

    def ready(self, result):
        try:
            self.callback(result)
        except Exception as err:
            if self.errorback:
                self.errorback(err)


class GeneratorFutureMock(Future):
    def __init__(self, coroutine, ioLoop=IOLoop.instance()):
        super(GeneratorFutureMock, self).__init__()
        self.coroutine = coroutine
        self.ioLoop = ioLoop

    def bind(self, callback, errorback=None, on_done=None):
        self.callback = callback
        self.errorback = errorback
        self.advance()

    def advance(self, value=None):
        try:
            result = self.coroutine.send(value)
            print(value, '->', result)

            ## wrap to future
            if isinstance(result, Future):
                future = result
            elif isinstance(result, Chain):
                chainFuture = FutureCallableMock()
                result.then(lambda r: chainFuture.ready(r.get()))
                future = chainFuture
            else:
                future = FutureMock(result, ioLoop=self.ioLoop)

            if result is not None:
                future.bind(self.advance)
        except StopIteration as err:
            print(StopIteration, err, value)
            self.callback(value)
        except Exception as err:
            print(Exception, err)
            self.errorback(err)


class ChainItem(object):
    def __init__(self, func, ioLoop=IOLoop.instance()):
        self.func = func
        self.ioLoop = ioLoop
        self.nextChainItem = None

    def execute(self, *args, **kwargs):
        try:
            future = self.func(*args, **kwargs)
            if isinstance(future, Future):
                pass
            elif isinstance(future, types.GeneratorType):
                future = GeneratorFutureMock(future, ioLoop=self.ioLoop)
            else:
                future = FutureMock(future, ioLoop=self.ioLoop)
            future.bind(self.callback, self.errorback)
        except (AssertionError, AttributeError, TypeError):
            raise
        except Exception as err:
            self.errorback(err)

    def callback(self, chunk):
        futureResult = FutureResult(chunk)
        if self.nextChainItem:
            self.ioLoop.add_callback(self.nextChainItem.execute, futureResult)
            # self.nextChainItem.execute(futureResult)

    def errorback(self, error):
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
            self.ioLoop.add_callback(chainItem.execute)
        self.chainItems.append(chainItem)
        return self


class AsynchronousApiTestCase(AsyncTestCase):
    def test_SingleChunk_SingleThen(self):
        expected = [
            lambda r: self.assertEqual(1, r.get()),
            lambda r: self.assertRaises(ChokeEvent, r.get),
        ]
        check = checker(expected, self)
        f = ServiceMock(chunks=[1], T=Chain, ioLoop=self.io_loop).execute()
        f.then(check)
        self.wait(timeout=0.5)
        self.assertTrue(len(expected) == 0)

    def test_MultipleChunks_SingleThen(self):
        expected = [
            lambda r: self.assertEqual(1, r.get()),
            lambda r: self.assertEqual(2, r.get()),
            lambda r: self.assertEqual(3, r.get()),
            lambda r: self.assertRaises(ChokeEvent, r.get),
        ]
        check = checker(expected, self)
        f = ServiceMock(chunks=[1, 2, 3], T=Chain, ioLoop=self.io_loop).execute()
        f.then(check)
        self.wait(timeout=0.5)
        self.assertTrue(len(expected) == 0)

    def test_SingleChunk_MultipleThen(self):
        expected = [
            lambda r: self.assertEqual(1, r.get()),
            lambda r: self.assertRaises(ChokeEvent, r.get),
        ]
        check = checker(expected, self)
        f = ServiceMock(chunks=[1], T=Chain, ioLoop=self.io_loop).execute()
        f.then(lambda r: r.get()).then(check)
        self.wait(timeout=0.5)
        self.assertTrue(len(expected) == 0)

    def test_MultipleChunks_MultipleThen(self):
        expected = [
            lambda r: self.assertEqual(1, r.get()),
            lambda r: self.assertEqual(2, r.get()),
            lambda r: self.assertEqual(3, r.get()),
            lambda r: self.assertRaises(ChokeEvent, r.get),
        ]
        check = checker(expected, self)
        f = ServiceMock(chunks=[1, 2, 3], T=Chain, ioLoop=self.io_loop).execute()
        f.then(lambda r: r.get()).then(check)
        self.wait(timeout=0.5)
        self.assertTrue(len(expected) == 0)

    def test_SingleSyncChunk_SingleThen(self):
        expected = [
            lambda r: self.assertEqual(1, r.get()),
        ]
        check = checker(expected, self)
        f = Chain([lambda: 1], ioLoop=self.io_loop)
        f.then(lambda r: r.get()).then(check)
        self.wait(timeout=0.5)
        self.assertTrue(len(expected) == 0)

    def test_SingleSyncChunk_MultipleThen(self):
        expected = [
            lambda r: self.assertEqual(2, r.get()),
        ]
        check = checker(expected, self)
        f = Chain([lambda: 1], ioLoop=self.io_loop)
        f.then(lambda r: r.get()).then(lambda r: r.get() + 1).then(check)
        self.wait(timeout=0.5)
        self.assertTrue(len(expected) == 0)

    def test_SingleErrorChunk_SingleThen(self):
        expected = [
            lambda r: self.assertRaises(Exception, r.get),
        ]
        check = checker(expected, self)

        def raiseException():
            raise Exception('Actual')

        f = Chain([raiseException], ioLoop=self.io_loop)
        f.then(check)
        self.wait(timeout=0.5)
        self.assertTrue(len(expected) == 0)

    def test_SingleErrorChunk_MultipleThen(self):
        expected = [
            lambda r: self.assertRaises(Exception, r.get),
        ]
        check = checker(expected, self)

        def raiseException():
            raise Exception('Actual')

        f = Chain([raiseException], ioLoop=self.io_loop)
        f.then(lambda r: r.get()).then(check)
        self.wait(timeout=0.5)
        self.assertTrue(len(expected) == 0)

    def test_SingleChunk_MultipleThen_Middleman(self):
        expected = [
            lambda r: self.assertEqual(2, r.get()),
        ]
        check = checker(expected, self)

        def middleMan(result):
            return result.get() + 1
        f = ServiceMock(chunks=[1], T=Chain, ioLoop=self.io_loop).execute()
        f.then(middleMan).then(check)
        self.wait(timeout=0.5)
        self.assertTrue(len(expected) == 0)

    def test_SingleChunk_MultipleThen_ErrorMiddleman(self):
        expected = [
            lambda r: self.assertRaises(Exception, r.get),
            lambda r: self.assertRaises(ChokeEvent, r.get),
        ]
        check = checker(expected, self)

        def middleMan(result):
            raise Exception('Middleman')
        f = ServiceMock(chunks=[1], T=Chain, ioLoop=self.io_loop).execute()
        f.then(middleMan).then(check)
        self.wait(timeout=0.5)
        self.assertTrue(len(expected) == 0)

    def test_MultipleChunks_MultipleThen_ErrorMiddleman(self):
        expected = [
            lambda r: self.assertEqual(1, r.get()),
            lambda r: self.assertRaises(Exception, r.get),
            lambda r: self.assertEqual(3, r.get()),
            lambda r: self.assertRaises(ChokeEvent, r.get),
        ]
        check = checker(expected, self)

        def middleMan(result):
            if result.get() == 2:
                raise Exception('Middleman')
            else:
                return result.get()
        f = ServiceMock(chunks=[1, 2, 3], T=Chain, ioLoop=self.io_loop).execute()
        f.then(middleMan).then(check)
        self.wait(timeout=0.5)
        self.assertTrue(len(expected) == 0)

    def test_SingleChunk_SingleThen_YieldMiddleman(self):
        expected = [
            lambda r: self.assertEqual(3, r.get()),
            lambda r: self.assertRaises(ChokeEvent, r.get),
        ]
        check = checker(expected, self)

        def middleMan(result):
            result.get()
            yield 'Any'
            yield 3
        f = ServiceMock(chunks=[1], T=Chain, ioLoop=self.io_loop).execute()
        f.then(middleMan).then(check)
        self.wait()
        self.assertTrue(len(expected) == 0)

    def test_MultipleChunk_SingleThen_YieldMiddleman(self):
        expected = [
            lambda r: self.assertEqual(3, r.get()),
            lambda r: self.assertEqual(3, r.get()),
            lambda r: self.assertEqual(3, r.get()),
            lambda r: self.assertRaises(ChokeEvent, r.get),
        ]
        check = checker(expected, self)

        def middleMan(result):
            result.get()
            yield 'Any'
            yield 3
        f = ServiceMock(chunks=[1, 2, 3], T=Chain, ioLoop=self.io_loop).execute()
        f.then(middleMan).then(check)
        self.wait()
        self.assertTrue(len(expected) == 0)

    def test_MultipleChunk_SingleThen_YieldAsyncMiddleman(self):
        expected = [
            lambda r: self.assertEqual([4, 5], r.get()),
            lambda r: self.assertEqual([4, 5], r.get()),
            lambda r: self.assertEqual([4, 5], r.get()),
            lambda r: self.assertRaises(ChokeEvent, r.get),
        ]
        check = checker(expected, self)

        def middleMan(result):
            result.get()
            s1 = yield ServiceMock(chunks=[4, 5], T=Chain, ioLoop=self.io_loop, interval=0.001).execute()
            s2 = yield
            yield [s1, s2]
        f = ServiceMock(chunks=[1, 2, 3], T=Chain, ioLoop=self.io_loop, interval=0.01).execute()
        f.then(middleMan).then(check)
        self.wait()
        self.assertTrue(len(expected) == 0)


if __name__ == '__main__':
    unittest.main()