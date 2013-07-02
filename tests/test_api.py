from __future__ import absolute_import

import hashlib
import time
import types
import unittest
import logging
from tornado.ioloop import IOLoop
from tornado.testing import AsyncTestCase
from cocaine.futures import Future
from cocaine.testing.mocks import ServiceMock, checker
from cocaine.exceptions import TimeoutError, ChokeEvent


__author__ = 'Evgeny Safronov <division494@gmail.com>'

ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(name)s: %(levelname)-8s: %(message)s')
ch.setFormatter(formatter)

logNames = [
    __name__,
    'cocaine.testing.mocks',
]

for logName in logNames:
    log = logging.getLogger(logName)
    log.setLevel(logging.DEBUG)
    log.propagate = False
    log.addHandler(ch)


class FutureResult(object):
    NONE_RESULT = hashlib.sha1('__None__')

    def __init__(self, result):
        self.result = result

    def isNone(self):
        return self.result == self.NONE_RESULT

    def get(self):
        return self._returnOrRaise(self.result)

    def reset(self):
        self.result = self.NONE_RESULT

    def getAndReset(self):
        result = self.result
        self.reset()
        return self._returnOrRaise(result)

    def _returnOrRaise(self, result):
        if isinstance(result, Exception):
            raise result
        else:
            return result

    @classmethod
    def NONE(cls):
        return FutureResult(cls.NONE_RESULT)


class FutureMock(Future):
    def __init__(self, result, ioLoop=None):
        super(FutureMock, self).__init__()
        self.result = result
        self.ioLoop = ioLoop or IOLoop.instance()
        self._bound = False

    def bind(self, callback, errorback=None, on_done=None):
        try:
            self.ioLoop.add_callback(callback, self.result)
        except Exception as err:
            self.ioLoop.add_callback(errorback, err)
        finally:
            self._bound = True

    def isBound(self):
        return self._bound

    def unbind(self):
        return


class FutureCallableMock(Future):
    def __init__(self):
        super(FutureCallableMock, self).__init__()
        self.unbind()

    def bind(self, callback, errorback=None, on_done=None):
        self.callback = callback
        self.errorback = errorback

    def unbind(self):
        self.callback = None
        self.errorback = None

    def isBound(self):
        return any([self.callback, self.errorback])

    def ready(self, result):
        if not self.isBound():
            return

        try:
            log.debug('FutureCallableMock.ready() - {0}({1})'.format(result, repr(result.result)))
            result = result.get()
            self.callback(result)
        except Exception as err:
            log.debug('FutureCallableMock.ready() Error - {0})'.format(repr(err)))
            if self.errorback:
                self.errorback(err)


class GeneratorFutureMock(Future):
    def __init__(self, coroutine, ioLoop=None):
        super(GeneratorFutureMock, self).__init__()
        self.coroutine = coroutine
        self.ioLoop = ioLoop or IOLoop.instance()
        self._currentFuture = None
        self.__chunks = []

    def bind(self, callback, errorback=None, on_done=None):
        self.callback = callback
        self.errorback = errorback
        self.advance()

    def advance(self, value=None):
        try:
            self.__chunks.append(value)
            result = self._next(value)
            future = self._wrapFuture(result)
            if result is not None:
                future.bind(self.advance, self.advance)
                #Todo: May be it is deprecated?:
                #if self._currentFuture and hasattr(self._currentFuture, 'isBound'):# and self._currentFuture.isBound():
                if self._currentFuture:
                    self._currentFuture.unbind()
                self._currentFuture = future
        except StopIteration:
            log.debug('GeneratorFutureMock.advance() - StopIteration caught. Value - {0}'.format(repr(value)))
            self.callback(value)
        except ChokeEvent as err:
            self.errorback(err)
        except Exception as err:
            log.debug('GeneratorFutureMock.advance - Error: {0}'.format(repr(err)))
            if self._currentFuture and self._currentFuture.isBound():
                self._currentFuture.unbind()
            self.errorback(err)
        finally:
            log.debug('Just for fun! Chunks - {0}. Current future - {1}'.format(self.__chunks, self._currentFuture))

    def _next(self, value):
        if isinstance(value, Exception):
            result = self.coroutine.throw(value)
        else:
            result = self.coroutine.send(value)
        log.debug('GeneratorFutureMock._next - {0} -> {1}'.format(repr(value), repr(result)))
        return result

    def _wrapFuture(self, result):
        if isinstance(result, Future):
            future = result
        elif isinstance(result, Chain):
            chainFuture = FutureCallableMock()
            result.then(lambda r: chainFuture.ready(r))
            future = chainFuture
        else:
            future = FutureMock(result, ioLoop=self.ioLoop)
        return future


class ChainItem(object):
    def __init__(self, func, ioLoop=None):
        self.func = func
        self.ioLoop = ioLoop or IOLoop.instance()
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
            # Rethrow programming errors
            raise
        except Exception as err:
            self.errorback(err)

    def callback(self, chunk):
        log.debug('ChainItem.callback - {0}'.format(repr(chunk)))
        futureResult = FutureResult(chunk)
        if self.nextChainItem:
            # Actually it does not matter if we invoke next chain item synchronously or not. But for convenience, let's
            # do it asynchronously.
            self.ioLoop.add_callback(self.nextChainItem.execute, futureResult)
            # self.nextChainItem.execute(futureResult)

    def errorback(self, error):
        self.callback(error)


class Chain(object):
    def __init__(self, functions=None, ioLoop=None):
        if not functions:
            functions = []
        self.ioLoop = ioLoop or IOLoop.instance()
        self.chainItems = []
        for func in functions:
            self.then(func)

        self._lastResult = FutureResult.NONE()

    def then(self, func):
        chainItem = ChainItem(func, self.ioLoop)
        if len(self.chainItems) > 0:
            self.chainItems[-1].nextChainItem = chainItem

        if len(self.chainItems) == 0:
            self.ioLoop.add_callback(chainItem.execute)
        self.chainItems.append(chainItem)
        return self

    def __nonzero__(self):
        return self.hasPendingResult()

    def hasPendingResult(self):
        return not self._lastResult.isNone()

    def get(self, timeout=None):
        """
        Do not mix asynchronous and synchronous chain usage! This one will stop event loop
        """
        self._checkTimeout(timeout)
        if self.hasPendingResult():
            return self._getLastResult()
        self._trackLastResult()

        if timeout:
            self.ioLoop.add_timeout(time.time() + timeout, lambda: self._saveLastResult(FutureResult(TimeoutError())))
        self.ioLoop.start()
        return self._getLastResult()

    def wait(self, timeout=None):
        self._checkTimeout(timeout)
        if self.hasPendingResult():
            return
        self._trackLastResult()
        if timeout:
            self.ioLoop.add_timeout(time.time() + timeout, lambda: self.ioLoop.stop())
        self.ioLoop.start()

    def __iter__(self):
        return self

    def next(self):
        try:
            return self.get()
        except ChokeEvent:
            raise StopIteration

    def _checkTimeout(self, timeout):
        if timeout is not None and timeout < 0.001:
            raise ValueError('Timeout can not be less then 1 ms')

    def _trackLastResult(self):
        if not self._isTrackingForLastResult():
            self.then(self._saveLastResult)

    def _saveLastResult(self, result):
        self._lastResult = result
        self.ioLoop.stop()

    def _isTrackingForLastResult(self):
        return self.chainItems[-1].func == self._saveLastResult

    def _getLastResult(self):
        if isinstance(self._lastResult.result, ChokeEvent):
            return self._lastResult.get()
        else:
            return self._lastResult.getAndReset()


# Actually testing is coming here

class AsynchronousApiTestCase(AsyncTestCase):
    T = Chain

    def test_SingleChunk_SingleThen(self):
        expected = [
            lambda r: self.assertEqual(1, r.get()),
            lambda r: self.assertRaises(ChokeEvent, r.get),
        ]
        check = checker(expected, self)
        f = ServiceMock(chunks=[1], T=self.T, ioLoop=self.io_loop).execute()
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
        f = ServiceMock(chunks=[1, 2, 3], T=self.T, ioLoop=self.io_loop).execute()
        f.then(check)
        self.wait(timeout=0.5)
        self.assertTrue(len(expected) == 0)

    def test_SingleChunk_MultipleThen(self):
        expected = [
            lambda r: self.assertEqual(2, r.get()),
            lambda r: self.assertRaises(ChokeEvent, r.get),
        ]
        check = checker(expected, self)
        f = ServiceMock(chunks=[1], T=self.T, ioLoop=self.io_loop).execute()

        def firstStep(futureResult):
            r = futureResult.get()
            return r * 2
        f.then(firstStep).then(check)
        self.wait(timeout=0.5)
        self.assertTrue(len(expected) == 0)

    def test_MultipleChunks_MultipleThen(self):
        expected = [
            lambda r: self.assertEqual(2, r.get()),
            lambda r: self.assertEqual(4, r.get()),
            lambda r: self.assertEqual(6, r.get()),
            lambda r: self.assertRaises(ChokeEvent, r.get),
        ]
        check = checker(expected, self)
        f = ServiceMock(chunks=[1, 2, 3], T=self.T, ioLoop=self.io_loop).execute()

        def firstStep(futureResult):
            r = futureResult.get()
            r *= 2
            return r
        f.then(firstStep).then(check)
        self.wait(timeout=0.5)
        self.assertTrue(len(expected) == 0)

    def test_SingleSyncChunk_SingleThen(self):
        expected = [
            lambda r: self.assertEqual(1, r.get()),
        ]
        check = checker(expected, self)
        f = Chain([lambda: 1], ioLoop=self.io_loop)
        f.then(check)
        self.wait(timeout=0.5)
        self.assertTrue(len(expected) == 0)

    def test_SingleSyncChunk_MultipleThen(self):
        expected = [
            lambda r: self.assertEqual(6, r.get()),
        ]
        check = checker(expected, self)
        f = Chain([lambda: 2], ioLoop=self.io_loop)

        def firstStep(futureResult):
            r = futureResult.get()
            r *= 3
            return r
        f.then(firstStep).then(check)
        self.wait(timeout=0.5)
        self.assertTrue(len(expected) == 0)

    def test_SingleErrorChunk_SingleThen(self):
        expected = [
            lambda r: self.assertRaises(Exception, r.get),
        ]
        check = checker(expected, self)

        def firstStep():
            raise Exception('Actual')

        f = Chain([firstStep], ioLoop=self.io_loop)
        f.then(check)
        self.wait(timeout=0.5)
        self.assertTrue(len(expected) == 0)

    def test_SingleErrorChunk_MultipleThen(self):
        expected = [
            lambda r: self.assertRaises(Exception, r.get),
        ]
        check = checker(expected, self)

        def firstStep():
            raise Exception('Actual')

        def secondStep(futureResult):
            futureResult.get()
            self.fail('This one should never be seen by anyone')

        f = Chain([firstStep], ioLoop=self.io_loop)
        f.then(secondStep).then(check)
        self.wait(timeout=0.5)
        self.assertTrue(len(expected) == 0)

    def test_SingleChunk_MultipleThen_Middleman(self):
        expected = [
            lambda r: self.assertEqual(2, r.get()),
        ]
        check = checker(expected, self)

        def middleMan(result):
            return result.get() + 1
        f = ServiceMock(chunks=[1], T=self.T, ioLoop=self.io_loop).execute()
        f.then(middleMan).then(check)
        self.wait(timeout=0.5)
        self.assertTrue(len(expected) == 0)

    def test_SingleChunk_MultipleThen_ErrorMiddleman(self):
        expected = [
            lambda r: self.assertRaises(ValueError, r.get),
            lambda r: self.assertRaises(ValueError, r.get),
        ]
        check = checker(expected, self)

        def middleMan(result):
            raise ValueError('Middleman')
        f = ServiceMock(chunks=[1], T=self.T, ioLoop=self.io_loop).execute()
        f.then(middleMan).then(check)
        self.wait(timeout=0.5)
        self.assertTrue(len(expected) == 0)

    def test_SingleChunk_MultipleThen_ErrorMiddlemanWithValueUnpacking(self):
        expected = [
            lambda r: self.assertRaises(ValueError, r.get),
            lambda r: self.assertRaises(ChokeEvent, r.get),
        ]
        check = checker(expected, self)

        def middleMan(result):
            result.get()
            raise ValueError('Middleman')
        f = ServiceMock(chunks=[1], T=self.T, ioLoop=self.io_loop).execute()
        f.then(middleMan).then(check)
        self.wait(timeout=0.5)
        self.assertTrue(len(expected) == 0)

    def test_MultipleChunks_MultipleThen_ErrorMiddleman(self):
        expected = [
            lambda r: self.assertEqual(2, r.get()),
            lambda r: self.assertRaises(ValueError, r.get),
            lambda r: self.assertEqual(6, r.get()),
            lambda r: self.assertRaises(ChokeEvent, r.get),
        ]
        check = checker(expected, self)

        def middleMan(result):
            if result.get() == 2:
                raise ValueError('Middleman')
            else:
                return result.get() * 2
        f = ServiceMock(chunks=[1, 2, 3], T=self.T, ioLoop=self.io_loop).execute()
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
            yield 'String that won\'t be seen by anyone'
            yield 3
        f = ServiceMock(chunks=[1], T=self.T, ioLoop=self.io_loop).execute()
        f.then(middleMan).then(check)
        self.wait()
        self.assertTrue(len(expected) == 0)

    def test_SingleChunk_MultipleChainItems_OnlyCoroutinesProcessing(self):
        expected = [
            lambda r: self.assertEqual(4, r.get()),
            lambda r: self.assertRaises(ChokeEvent, r.get),
        ]
        check = checker(expected, self)

        def firstStep(result):
            r = result.get()
            yield 'String that won\'t be seen by anyone'
            yield r * 2

        def secondStep(result):
            yield result.get() * 2

        f = ServiceMock(chunks=[1], T=self.T, ioLoop=self.io_loop).execute()
        f.then(firstStep).then(secondStep).then(check)
        self.wait()
        self.assertTrue(len(expected) == 0)

    def test_SingleChunk_MultipleChainItems_MixedProcessing1(self):
        expected = [
            lambda r: self.assertEqual(6, r.get()),
            lambda r: self.assertRaises(ChokeEvent, r.get),
        ]
        check = checker(expected, self)

        def firstStep(result):
            r = result.get()
            return r * 2

        def secondStep(result):
            yield result.get() * 3

        f = ServiceMock(chunks=[1], T=self.T, ioLoop=self.io_loop).execute()
        f.then(firstStep).then(secondStep).then(check)
        self.wait()
        self.assertTrue(len(expected) == 0)

    def test_SingleChunk_MultipleChainItems_MixedProcessing2(self):
        expected = [
            lambda r: self.assertEqual(6, r.get()),
            lambda r: self.assertRaises(ChokeEvent, r.get),
        ]
        check = checker(expected, self)

        def firstStep(result):
            yield result.get() * 3

        def secondStep(result):
            r = result.get()
            return r * 2

        f = ServiceMock(chunks=[1], T=self.T, ioLoop=self.io_loop).execute()
        f.then(firstStep).then(secondStep).then(check)
        self.wait()
        self.assertTrue(len(expected) == 0)

    def test_MultipleChunk_SingleThen_YieldMiddleman(self):
        expected = [
            lambda r: self.assertEqual(3, r.get()),
            lambda r: self.assertEqual(6, r.get()),
            lambda r: self.assertEqual(9, r.get()),
            lambda r: self.assertRaises(ChokeEvent, r.get),
        ]
        check = checker(expected, self)

        def middleMan(result):
            r = result.get()
            yield 'This string won\'t be seen by anyone'
            yield r * 3
        f = ServiceMock(chunks=[1, 2, 3], T=self.T, ioLoop=self.io_loop).execute()
        f.then(middleMan).then(check)
        self.wait()
        self.assertTrue(len(expected) == 0)

    def test_MultipleChunk_SingleThen_YieldAsyncMiddleman(self):
        expected = [
            lambda r: self.assertEqual([1, 2], r.get()),
            lambda r: self.assertEqual([2, 3], r.get()),
            lambda r: self.assertEqual([3, 4], r.get()),
            lambda r: self.assertRaises(ChokeEvent, r.get),
        ]
        check = checker(expected, self)

        def middleMan(result):
            r = result.get()
            s1 = yield ServiceMock(chunks=[r, r + 1], T=self.T, ioLoop=self.io_loop, interval=0.001).execute()
            s2 = yield
            yield [s1, s2]
        f = ServiceMock(chunks=[1, 2, 3], T=self.T, ioLoop=self.io_loop, interval=0.01).execute()
        f.then(middleMan).then(check)
        self.wait()
        self.assertTrue(len(expected) == 0)

    def test_SingleChunk_SingleThen_YieldAsyncDoubleMiddlemanWithLessChunks(self):
        expected = [
            lambda r: self.assertEqual([4, 5, 6], r.get()),
            lambda r: self.assertRaises(ChokeEvent, r.get),
        ]
        check = checker(expected, self)

        def middleMan(result):
            result.get()
            s1 = yield ServiceMock(chunks=[4, 5], T=self.T, ioLoop=self.io_loop, interval=0.002).execute()
            s2 = yield
            s3 = yield ServiceMock(chunks=[6], T=self.T, ioLoop=self.io_loop, interval=0.001).execute()
            yield [s1, s2, s3]
        f = ServiceMock(chunks=[1], T=self.T, ioLoop=self.io_loop, interval=0.01).execute()
        f.then(middleMan).then(check)
        self.wait()
        self.assertTrue(len(expected) == 0)

    def test_SingleChunk_SingleThen_YieldAsyncDoubleMiddlemanWithMoreChunks(self):
        expected = [
            lambda r: self.assertEqual([4, 5, 6, 7, 8], r.get()),
            lambda r: self.assertRaises(ChokeEvent, r.get),
        ]
        check = checker(expected, self)

        def middleMan(result):
            result.get()
            s1 = yield ServiceMock(chunks=[4, 5], T=self.T, ioLoop=self.io_loop, interval=0.001).execute()
            s2 = yield
            s3 = yield ServiceMock(chunks=[6, 7, 8], T=self.T, ioLoop=self.io_loop, interval=0.001).execute()
            s4 = yield
            s5 = yield
            yield [s1, s2, s3, s4, s5]
        f = ServiceMock(chunks=[1], T=self.T, ioLoop=self.io_loop, interval=0.01).execute()
        f.then(middleMan).then(check)
        self.wait()
        self.assertTrue(len(expected) == 0)

    def test_YieldAsyncMiddlemanExtraChunkResultsInChokeEvent(self):
        expected = [
            lambda r: self.assertRaises(ChokeEvent, r.get),
            lambda r: self.assertRaises(ChokeEvent, r.get),
        ]
        check = checker(expected, self)

        def middleMan(result):
            result.get()
            s1 = yield ServiceMock(chunks=[4, 5], T=self.T, ioLoop=self.io_loop, interval=0.001).execute()
            s2 = yield
            # This one will lead to the ChokeEvent
            s3 = yield
            yield [s1, s2, s3]
        f = ServiceMock(chunks=[1], T=self.T, ioLoop=self.io_loop, interval=0.01).execute()
        f.then(middleMan).then(check)
        self.wait()
        self.assertTrue(len(expected) == 0)

    def test_YieldAsyncMiddlemanExtraChunksResultsInChokeEventForever(self):
        expected = [
            lambda r: self.assertRaises(ChokeEvent, r.get),
            lambda r: self.assertRaises(ChokeEvent, r.get),
        ]
        check = checker(expected, self)

        def middleMan(result):
            result.get()
            s1 = yield ServiceMock(chunks=[4, 5], T=self.T, ioLoop=self.io_loop, interval=0.001).execute()
            s2 = yield
            # This one will lead to the ChokeEvent
            s3 = yield
            s4 = yield
            yield [s1, s2, s3, s4]
        f = ServiceMock(chunks=[1], T=self.T, ioLoop=self.io_loop, interval=0.01).execute()
        f.then(middleMan).then(check)
        self.wait()
        self.assertTrue(len(expected) == 0)

    def test_MultipleChunk_SingleThen_YieldErrorMiddleman(self):
        expected = [
            lambda r: self.assertEqual(1, r.get()),
            lambda r: self.assertRaises(Exception, r.get),
            lambda r: self.assertEqual(3, r.get()),
            lambda r: self.assertRaises(ChokeEvent, r.get),
        ]
        check = checker(expected, self)

        def middleMan(result):
            r = result.get()
            if r == 2:
                raise Exception('=(')
            yield r
        f = ServiceMock(chunks=[1, 2, 3], T=self.T, ioLoop=self.io_loop).execute()
        f.then(middleMan).then(check)
        self.wait()
        self.assertTrue(len(expected) == 0)

    def test_MultipleChunk_SingleThen_YieldAsyncErrorMiddleman(self):
        expected = [
            lambda r: self.assertRaises(Exception, r.get),
            lambda r: self.assertRaises(Exception, r.get),
            lambda r: self.assertRaises(Exception, r.get),
            lambda r: self.assertRaises(ChokeEvent, r.get),
        ]
        check = checker(expected, self)

        def middleMan(result):
            result.get()
            s1 = yield ServiceMock(chunks=[4, Exception(), 6], T=self.T, ioLoop=self.io_loop, interval=0.001).execute()
            # Here exception comes
            s2 = yield
            s3 = yield
            print('This should not be seen!', s1, s2, s3)
            yield 1
        f = ServiceMock(chunks=[1, 2, 3], T=self.T, ioLoop=self.io_loop).execute()
        f.then(middleMan).then(check)
        self.wait()
        self.assertTrue(len(expected) == 0)


class SynchronousApiTestCase(AsyncTestCase):
    T = Chain

    def test_GetSingleChunk(self):
        f = ServiceMock(chunks=[1], T=self.T, ioLoop=self.io_loop).execute()
        r = f.get()
        self.assertEqual(1, r)

    def test_GetMultipleChunks(self):
        f = ServiceMock(chunks=[1, 2, 3], T=self.T, ioLoop=self.io_loop).execute()
        r1 = f.get()
        r2 = f.get()
        r3 = f.get()
        self.assertEqual(1, r1)
        self.assertEqual(2, r2)
        self.assertEqual(3, r3)

    def test_GetSingleErrorChunk(self):
        f = ServiceMock(chunks=[Exception('Oops')], T=self.T, ioLoop=self.io_loop).execute()
        self.assertRaises(Exception, f.get)

    def test_GetMultipleErrorChunks(self):
        f = ServiceMock(chunks=[ValueError('Oops1'), IOError('Oops2')], T=self.T, ioLoop=self.io_loop).execute()
        self.assertRaises(ValueError, f.get)
        self.assertRaises(IOError, f.get)

    def test_GetMultipleMixChunks(self):
        f = ServiceMock(chunks=[ValueError('Oops1'), 1, IOError('Oops2')], T=self.T, ioLoop=self.io_loop).execute()
        self.assertRaises(ValueError, f.get)
        self.assertEqual(1, f.get())
        self.assertRaises(IOError, f.get)

    def test_GetMultipleMixChunksWithComplexChain(self):
        def middleMan(result):
            r = result.get()
            if r == 2:
                raise Exception('=(')
            yield r
        f = ServiceMock(chunks=[1, 2, 3], T=self.T, ioLoop=self.io_loop).execute()
        f.then(middleMan)
        self.assertEqual(1, f.get())
        self.assertRaises(Exception, f.get)
        self.assertEqual(3, f.get())

    def test_GetSingleChunkTimeout(self):
        f = ServiceMock(chunks=[1], T=self.T, ioLoop=self.io_loop, interval=0.2).execute()
        self.assertRaises(TimeoutError, f.get, 0.1)

    def test_GetValueErrors(self):
        f = ServiceMock(chunks=[1], T=self.T, ioLoop=self.io_loop).execute()
        self.assertRaises(ValueError, f.get, 0)
        self.assertRaises(ValueError, f.get, -1.0)
        self.assertRaises(ValueError, f.get, 0.0009)
        self.assertRaises(TypeError, f.get, 'str')
        self.assertRaises(TypeError, f.get, '0.1')

    def test_GetExtraChunksResultsInChokeEvent(self):
        f = ServiceMock(chunks=[1], T=self.T, ioLoop=self.io_loop).execute()
        r = f.get()
        self.assertEqual(1, r)
        self.assertRaises(ChokeEvent, f.get)
        self.assertRaises(ChokeEvent, f.get)

    def test_GetSingleChunkAfterWaiting(self):
        f = ServiceMock(chunks=[1], T=self.T, ioLoop=self.io_loop).execute()
        f.wait()
        r = f.get()
        self.assertEqual(1, r)

    def test_GetSingleChunkAfterMultipleWaiting(self):
        f = ServiceMock(chunks=[1], T=self.T, ioLoop=self.io_loop).execute()
        f.wait()
        f.wait()
        f.wait()
        r = f.get()
        self.assertEqual(1, r)

    def test_GetMultipleChunksAfterMultipleWaiting(self):
        f = ServiceMock(chunks=[1, 2, 3], T=self.T, ioLoop=self.io_loop).execute()
        f.wait()
        f.wait()
        r1 = f.get()
        f.wait()
        f.wait()
        f.wait()
        r2 = f.get()
        r3 = f.get()
        self.assertEqual(1, r1)
        self.assertEqual(2, r2)
        self.assertEqual(3, r3)

    def test_HasPendingResult(self):
        f = ServiceMock(chunks=[1], T=self.T, ioLoop=self.io_loop).execute()
        self.assertFalse(f.hasPendingResult())
        f.wait()
        self.assertTrue(f.hasPendingResult())

    def test_MagicHasPendingResult(self):
        f = ServiceMock(chunks=[1], T=self.T, ioLoop=self.io_loop).execute()
        self.assertFalse(bool(f))
        f.wait()
        self.assertTrue(bool(f))

    def test_WaitWithTimeout(self):
        f = ServiceMock(chunks=[1], T=self.T, ioLoop=self.io_loop, interval=0.1).execute()
        f.wait(0.050)
        self.assertTrue(f._lastResult.isNone())
        f.wait(0.040)
        self.assertTrue(f._lastResult.isNone())
        f.wait(0.011)
        self.assertFalse(f._lastResult.isNone())

    def test_Generator(self):
        f = ServiceMock(chunks=[1, 2, 3], T=self.T, ioLoop=self.io_loop).execute()
        collect = []
        for r in f:
            collect.append(r)
        self.assertEqual([1, 2, 3], collect)

    def test_PartialGenerator(self):
        f = ServiceMock(chunks=[1, 2, 3], T=self.T, ioLoop=self.io_loop).execute()
        collect = [f.get()]
        for r in f:
            collect.append(r)
        self.assertEqual([1, 2, 3], collect)


if __name__ == '__main__':
    unittest.main()