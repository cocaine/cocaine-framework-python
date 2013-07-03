import hashlib
from multiprocessing import Process
from multiprocessing.pool import Pool
from threading import Thread
import time
import types
from tornado.ioloop import IOLoop
from cocaine.exceptions import ChokeEvent, TimeoutError
from cocaine.futures import Future
import logging

__author__ = 'Evgeny Safronov <division494@gmail.com>'


log = logging.getLogger(__name__)


class FutureResult(object):
    """
    Represents future result and provides methods to obtain this result, manipulate or reset.

    The result itself can be any object or exception. If some exception is stored, then it will be thrown after user
    invokes `get` method.
    Note, that `NoneType` is also some result, so it cannot be used as mark to store uninitialized future result.
    You can call `FutureResult.NONE()` constructor if an empty uninitialized result is needed.
    """
    NONE_RESULT = hashlib.sha1('__None__')

    def __init__(self, result):
        self.result = result

    def isNone(self):
        """
        Checks if there is some result stored in this object.

        >>> FutureResult(1).isNone()
        False
        >>> FutureResult.NONE().isNone()
        True
        """
        return self.result == self.NONE_RESULT

    def get(self):
        """
        Extracts future result from object.

        If an exception is stored in this object, than it will be raised, so surround dangerous code with try/except
        blocks.

        >>> FutureResult(1).get()
        1
        >>> FutureResult(ValueError('ErrorMessage')).get()
        Traceback (most recent call last):
        ...
        ValueError: ErrorMessage
        """
        return self._returnOrRaise(self.result)

    def reset(self):
        """
        Clears stored result and set it to the uninitialized state.

        >>> r = FutureResult(1)
        >>> r.reset()
        >>> r.isNone()
        True
        """
        self.result = self.NONE_RESULT

    def getAndReset(self):
        """
        Extracts future result from object and resets it to the uninitialized state.

        If an exception is stored in this object, than it will be raised, so surround dangerous code with try/except
        blocks. Anyway, it is guaranteed that stored result object will be reset.

        >>> r = FutureResult(1)
        >>> r.getAndReset()
        1
        >>> r.isNone()
        True
        """
        result = self.result
        self.reset()
        return self._returnOrRaise(result)

    @classmethod
    def NONE(cls):
        """
        Constructs uninitialized future result object.

        >>> FutureResult.NONE().isNone()
        True
        """
        return FutureResult(cls.NONE_RESULT)

    def _returnOrRaise(self, result):
        if isinstance(result, Exception):
            raise result
        else:
            return result


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


class ConcurrentWorker(object):
    def __init__(self, func, ioLoop=None, *args, **kwargs):
        self.func = func
        self.ioLoop = ioLoop or IOLoop.instance()
        self.args = args
        self.kwargs = kwargs

        self.worker = Thread(target=self._run)
        self.worker.setDaemon(True)
        self.callback = None

    def _run(self):
        try:
            result = self.func(*self.args, **self.kwargs)
            self.callback(result)
        except Exception as err:
            self.callback(err)

    def runBackground(self, callback):
        def onDone(result):
            self.ioLoop.add_callback(lambda: callback(FutureResult(result)))
        self.callback = onDone
        self.worker.start()


class GeneratorFutureMock(Future):
    def __init__(self, coroutine, ioLoop=None):
        super(GeneratorFutureMock, self).__init__()
        self.coroutine = coroutine
        self.ioLoop = ioLoop or IOLoop.instance()
        self._currentFuture = None
        self._chunks = []
        self._results = []

    def bind(self, callback, errorback=None, on_done=None):
        self.callback = callback
        self.errorback = errorback
        self.advance()

    def advance(self, value=None):
        try:
            self._chunks.append(value)
            result = self._next(value)
            future = self._wrapFuture(result)

            if result is not None:
                log.debug('GeneratorFutureMock.advance() - Binding future {0} instead of {1}'.format(
                    future, self._currentFuture))
                future.bind(self.advance, self.advance)
                if self._currentFuture:
                    self._currentFuture.unbind()
                self._currentFuture = future
        except StopIteration:
            log.debug('GeneratorFutureMock.advance() - StopIteration caught. Value - {0}'.format(repr(value)))
            self.callback(value)
        except ChokeEvent as err:
            log.debug('GeneratorFutureMock.advance() - ChokeEvent caught. Value - {0}'.format(repr(value)))
            self.errorback(err)
        except Exception as err:
            log.debug('GeneratorFutureMock.advance - Error: {0}'.format(repr(err)))
            if self._currentFuture and self._currentFuture.isBound():
                self._currentFuture.unbind()
            self.errorback(err)
        finally:
            log.debug('Just for fun! Chunks - {0}. Current future - {1}'.format(self._chunks, self._currentFuture))

    def _next(self, value):
        if isinstance(value, ChokeEvent):
            if self._results and self._results[-1] is None:
                result = self.coroutine.throw(ChokeEvent())
            else:
                result = self.coroutine.send(None)
        elif isinstance(value, Exception):
            result = self.coroutine.throw(value)
        else:
            result = self.coroutine.send(value)
        self._results.append(result)
        log.debug('GeneratorFutureMock._next() - {0} -> {1}'.format(repr(value), repr(result)))
        return result

    def _wrapFuture(self, result):
        if isinstance(result, Future):
            future = result
        elif isinstance(result, Chain):
            chainFuture = FutureCallableMock()
            result.then(lambda r: chainFuture.ready(r))
            future = chainFuture
        elif isinstance(result, ConcurrentWorker):
            concurrentFuture = FutureCallableMock()
            result.runBackground(lambda r: concurrentFuture.ready(r))
            future = concurrentFuture
        else:
            future = FutureMock(result, ioLoop=self.ioLoop)
        log.debug('GeneratorFutureMock._wrap() - {0} -> {1}'.format(result, future))
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
        log.debug('ChainItem.errorback - {0}'.format(repr(error)))
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

    def run(self):
        pass

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


def concurrent(func):
    """
    Wraps function or method, so it can be invoked concurrently by yielding in chain context.

    Program control will be returned to the yield statement once processing is done. Current implementation invokes
    function in separate thread.
    """
    def wrapper(*args, **kwargs):
        mock = ConcurrentWorker(func, *args, **kwargs)
        return mock
    return wrapper
