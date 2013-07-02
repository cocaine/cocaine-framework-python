import hashlib
import time
import types
from tornado.ioloop import IOLoop
from cocaine.exceptions import ChokeEvent, TimeoutError
from cocaine.futures import Future
import logging

__author__ = 'Evgeny Safronov <division494@gmail.com>'


log = logging.getLogger(__name__)


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
                log.debug('GeneratorFutureMock.advance() - Result is None. Binding future {0} instead of {1}'.format(
                    future, self._currentFuture))
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
            log.debug('GeneratorFutureMock.advance() - ChokeEvent caught. Value - {0}'.format(repr(value)))
            self.errorback(err)
        except Exception as err:
            log.debug('GeneratorFutureMock.advance - Error: {0}'.format(repr(err)))
            if self._currentFuture and self._currentFuture.isBound():
                self._currentFuture.unbind()
            self.errorback(err)
        finally:
            log.debug('Just for fun! Chunks - {0}. Current future - {1}'.format(self.__chunks, self._currentFuture))

    def _next(self, value):
        if isinstance(value, ChokeEvent):
            print(self.__chunks)
            result = self.coroutine.send(None)
        elif isinstance(value, Exception):
            result = self.coroutine.throw(value)
        else:
            result = self.coroutine.send(value)
        log.debug('GeneratorFutureMock._next() - {0} -> {1}'.format(repr(value), repr(result)))
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
        log.debug('GeneratorFutureMock._wrap() - {0} -> {1}'.format(result, future))
        return future


class ChainItem(object):
    def __init__(self, func, ioLoop=None):
        self.func = func
        self.ioLoop = ioLoop or IOLoop.instance()
        self.nextChainItem = None
        self.__cache = []

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
            self.__cache.append(future)
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


def threaded(func):
    def wrapper(*args, **kwargs):
        # mock = ThreadWorker(func, *args, **kwargs)
        # return mock
        raise NotImplementedError
    return wrapper