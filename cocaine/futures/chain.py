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
    """

    def __init__(self, result):
        self.result = result

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
        self.log = logging.getLogger(self.__module__ + '.' + self.__class__.__name__)

    def execute(self, *args, **kwargs):
        try:
            self.log.debug('{0:x} : Executing {1} with {2}'.format(id(self), self.func,
                                                                   [repr(arg.result) for arg in args]))
            future = self.func(*args, **kwargs)
            self.log.debug('{0:x}: Execution done. Received - {2}'.format(id(self), self.func, future))
            if isinstance(future, Future):
                pass
            elif isinstance(future, types.GeneratorType):
                future = GeneratorFutureMock(future, ioLoop=self.ioLoop)
            else:
                future = FutureMock(future, ioLoop=self.ioLoop)
            self.log.debug('{0:x}: Binding future {1}'.format(id(self), future))
            future.bind(self.callback, self.errorback)
        except (AssertionError, AttributeError, TypeError):
            # Rethrow programming errors
            raise
        except Exception as err:
            self.errorback(err)

    def callback(self, chunk):
        self.log.debug('{0:x}: ChainItem.callback - {1}'.format(id(self), repr(chunk)))
        futureResult = FutureResult(chunk)
        if self.nextChainItem:
            # Actually it does not matter if we invoke next chain item synchronously or not. But for convenience, let's
            # do it asynchronously.
            self.ioLoop.add_callback(self.nextChainItem.execute, futureResult)
            # self.nextChainItem.execute(futureResult)

    def errorback(self, error):
        self.log.debug('{0:x}: ChainItem.errorback - {1}'.format(id(self), repr(error)))
        self.callback(error)


class Chain(object):
    """
    Represents pipeline of processing functions over chunks.

    This class represents chain of processing functions over incoming chunks. It manages creating chunk pipeline by
    binding them one-by-one.
    Incoming chunks will be processed separately in direct order.
    If some of processing function fails and raise an exception, it will be transported to the next chain item over and
    over again until it will be caught by `except` block or transferred to the event loop exception trap.

    There is also synchronous API provided, but it should be used only for scripting or tests.
    """
    def __init__(self, functions=None, ioLoop=None):
        """
        Initializes chain object.

        There is `functions` parameter provided for that case, when you can explicitly define chunk source and,
        probably, some processing functions.
        Event loop can also be injected. If no event loop specified (default), it will be initialized as tornado io
        event loop singleton.

        :param functions: optional list of processing functions.
        :param ioLoop: specified event loop. By default, it is initialized by tornado io event loop global instance.
        """
        if not functions:
            functions = []
        self.ioLoop = ioLoop or IOLoop.instance()
        self.log = logging.getLogger(self.__module__ + '.' + self.__class__.__name__)
        self.chainItems = []
        for func in functions:
            self.then(func)

        self._lastResults = []

    def then(self, func):
        """
        Puts specified chunk processing function into chain pipeline.

        With this method, you can create a pipeline of several chunk handlers. Chunks will be processed asynchronously,
        transported after that to the next chain item.
        If some error occurred in the middle of chain and no one caught it, it will be redirected next over pipeline,
        so make sure you catch all exceptions you need and correctly process it.

        :param func: chunk processing function or method. Its signature must have one parameter of class `FutureResult`
                     if specified function is not the chunk source. If function is chunk source (i.e. service execution
                     method) than there is no parameters must be provided in function signature.
        """
        self.log.debug('Adding function "{0}" to the chain'.format(func))
        chainItem = ChainItem(func, self.ioLoop)

        if len(self.chainItems) == 0:
            self.log.debug('Executing first chain item asynchronously - {0}'.format(chainItem))
            self.ioLoop.add_callback(chainItem.execute)
        else:
            self.log.debug('Coupling {0} to {1}'.format(chainItem, self.chainItems[-1]))
            self.chainItems[-1].nextChainItem = chainItem

        self.chainItems.append(chainItem)
        return self

    def run(self):
        pass

    def __nonzero__(self):
        """
        Chain object is treat as nonzero if it has some pending result.
        """
        return self.hasPendingResult()

    def hasPendingResult(self):
        """
        Provides information if chain object has pending result that can be taken from it.
        """
        return len(self._lastResults) > 0

    def get(self, timeout=None):
        """
        Returns next result of chaining execution. If chain haven't been completed after `timeout` seconds, an
        `TimeoutError` will be raised.

        Default implementation simply starts event loop, sets timeout condition and run chain expression. Event loop
        will be stopped after getting chain result or after timeout expired.
        It is correct to call this method multiple times to receive multiple chain results until you exactly know
        how much chunks there will be. A `ChokeEvent` will be raised if there is no more chunks to process.

        Warning: This is synchronous usage of chain object. Do not mix asynchronous and synchronous chain usage!

        :param timeout: Timeout in seconds after which TimeoutError will be raised. If timeout is not set (default) it
                        means forever waiting.
        :raises ChokeEvent: If there is no more chunks to process.
        :raises ValueError: If timeout is set and it is less than 1 ms.
        :raises TimeoutError: If timeout expired.
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
        """
        Waits chaining execution during some time or forever.

        This method provides you nice way to do asynchronous waiting future result from chain expression. Default
        implementation simply starts event loop, sets timeout condition and run chain expression. Event loop will be
        stopped after getting final chain result or after timeout expired. Unlike `get` method there will be no
        exception raised if timeout is occurred while chaining execution running.

        Warning: This is synchronous usage of chain object. Do not mix asynchronous and synchronous chain usage!

        :param timeout: Timeout in seconds after which event loop will be stopped. If timeout is not set (default) it
                        means forever waiting.
        :raises ValueError: If timeout is set and it is less than 1 ms.
        """
        self._checkTimeout(timeout)
        if self.hasPendingResult():
            return
        self._trackLastResult()
        if timeout:
            self.ioLoop.add_timeout(time.time() + timeout, lambda: self.ioLoop.stop())
        self.ioLoop.start()

    def __iter__(self):
        """
        Traits chain object as iterator. Note, that iterator can be used only once. Normally, you should not use this
        method directly - python uses it automatically in the `for` loop.

        Warning: This is synchronous usage of chain object. Do not mix asynchronous and synchronous chain usage!
        """
        return self

    def next(self):
        """
        Gets next chain result. Normally, you should not use this method directly - python uses it automatically in
        the `for` loop.

        Warning: This is synchronous usage of chain object. Do not mix asynchronous and synchronous chain usage!
        """
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
        self._lastResults.append(result)
        self.ioLoop.stop()

    def _isTrackingForLastResult(self):
        return self.chainItems[-1].func == self._saveLastResult

    def _getLastResult(self):
        assert len(self._lastResults) > 0

        lastResult = self._lastResults[0]
        if isinstance(lastResult.result, ChokeEvent):
            return lastResult.get()
        else:
            self._lastResults.pop(0)
            return lastResult.get()


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
