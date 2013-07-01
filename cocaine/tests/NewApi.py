import hashlib
import time
import types
import unittest
from tornado.ioloop import IOLoop
from tornado.testing import AsyncTestCase
from cocaine.futures import Future
from cocaine.futures.chain import ChainFactory
from cocaine.exceptions import TimeoutError

__author__ = 'Evgeny Safronov <division494@gmail.com>'


class Tests(object):
    DEBUG = True


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
            if isinstance(chunk, Exception):
                self.errorback(chunk)
            else:
                self.callback(chunk)

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
            if Tests.DEBUG:
                print('>>>>>>>>>>>>>>>>>>>>>>>>>> R', result.result)
            condition(result)
        except AssertionError as err:
            if Tests.DEBUG:
                print('>>>>>>>>>>>>>>>>>>>>>>>>>> R Assert Error', result.result, err)
            exit(1)
        finally:
            if not conditions:
                self.stop()
    return check

# =====================================================================================================================


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
    def __init__(self, result, ioLoop=IOLoop.instance()):
        super(FutureMock, self).__init__()
        self.result = result
        self.ioLoop = ioLoop
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
            print('---1', result, result.result)
            result = result.get()
            self.callback(result)
        except Exception as err:
            print('---2', err)
            if self.errorback:
                self.errorback(err)


class GeneratorFutureMock(Future):
    def __init__(self, coroutine, ioLoop=IOLoop.instance()):
        super(GeneratorFutureMock, self).__init__()
        self.coroutine = coroutine
        self.ioLoop = ioLoop
        self.__chunks = []
        self.__future = None

    def bind(self, callback, errorback=None, on_done=None):
        self.callback = callback
        self.errorback = errorback
        self.advance()

    def advance(self, value=None):
        try:
            self.__chunks.append(value)
            if isinstance(value, Exception):
                result = self.coroutine.throw(value)
            else:
                result = self.coroutine.send(value)
            print(value, '->', result)

            ## wrap to future
            if isinstance(result, Future):
                future = result
            elif isinstance(result, Chain):
                chainFuture = FutureCallableMock()
                result.then(lambda r: chainFuture.ready(r))
                future = chainFuture
            else:
                future = FutureMock(result, ioLoop=self.ioLoop)

            if result is not None:
                future.bind(self.advance, self.advance)
                if self.__future and hasattr(self.__future, 'isBound') and self.__future.isBound():
                    self.__future.unbind()
                self.__future = future
        except StopIteration as err:
            print('StopIteration', StopIteration, err, value)
            self.callback(value)
        except ChokeEvent as err:
            self.errorback(err)
        except Exception as err:
            print('Exception', Exception, err)
            if self.__future and self.__future.isBound():
                self.__future.unbind()
            self.errorback(err)
        finally:
            print('C & F', self.__chunks, self.__future)


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
            # Rethrow programming errors
            raise
        except Exception as err:
            self.errorback(err)

    def callback(self, chunk):
        print('cb', chunk)
        futureResult = FutureResult(chunk)
        if self.nextChainItem:
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
            lambda r: self.assertEqual(1, r.get()),
            lambda r: self.assertRaises(ChokeEvent, r.get),
        ]
        check = checker(expected, self)
        f = ServiceMock(chunks=[1], T=self.T, ioLoop=self.io_loop).execute()
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
        f = ServiceMock(chunks=[1, 2, 3], T=self.T, ioLoop=self.io_loop).execute()
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
        f = ServiceMock(chunks=[1], T=self.T, ioLoop=self.io_loop).execute()
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
        f = ServiceMock(chunks=[1], T=self.T, ioLoop=self.io_loop).execute()
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
            yield 'Any'
            yield 3
        f = ServiceMock(chunks=[1], T=self.T, ioLoop=self.io_loop).execute()
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
        f = ServiceMock(chunks=[1, 2, 3], T=self.T, ioLoop=self.io_loop).execute()
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
            s1 = yield ServiceMock(chunks=[4, 5], T=self.T, ioLoop=self.io_loop, interval=0.001).execute()
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
            s1 = yield ServiceMock(chunks=[4, 5], T=self.T, ioLoop=self.io_loop, interval=0.001).execute()
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
            print('s1', s1)
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
        f.wait(0.049)
        self.assertTrue(f._lastResult.isNone())
        f.wait(0.001)
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