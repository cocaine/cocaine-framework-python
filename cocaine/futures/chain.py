import collections
import time
import types
import logging
import sys
from threading import Thread

from tornado.ioloop import IOLoop
from tornado.util import raise_exc_info

from cocaine.exceptions import ChokeEvent
from cocaine.asio.exceptions import TimeoutError
from cocaine.futures import Future


__author__ = 'Evgeny Safronov <division494@gmail.com>'


log = logging.getLogger('cocaine.errors')


class FutureResult(object):
    """
    Represents future result and provides methods to obtain this result, manipulate or reset.

    The result itself can be any object or exception. If some exception is stored, then it will be thrown after user
    invokes `get` method.
    """

    def __init__(self, result):
        self.result = result
        self._exc_info = None
        if isinstance(result, Exception) and not (isinstance(result, ChokeEvent) or isinstance(result, StopIteration)):
            self._exc_info = sys.exc_info()

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
            if self._exc_info is not None:
                exc_type, exc_value, tb = self._exc_info
                if all([exc_type, exc_value, tb]):
                    raise_exc_info(self._exc_info)
            raise result
        else:
            return result


class PreparedFuture(Future):
    """Represents prepared future object with in advance known result.

    It is useful when you need to return already defined result from function and to use that function in some future
    context (like chain).

    Specified callback or errorback will be triggered on the next event loop turn after `bind` method is invoked.

    Note: While in chain context, you don't need to use it directly - if you return something from function that meant
    to be used as chain item, the result will be automatically wrapped with `PreparedFuture`.
    """
    def __init__(self, result, ioLoop=None):
        super(PreparedFuture, self).__init__()
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


class Deferred(Future):
    """Deferred future result.

    This class represents deferred result of asynchronous operation. It is designed specially for returning from
    function that is like to be used in Chain context.

    Typical usage assumes that you create `Deferred` object, keep it somewhere, start asynchronous operation and
    return this deferred from function. When asynchronous operation is done, just invoke `ready` and pass the result
    (including Exceptions) into it.

    Here the example of asynchronous function that starts timer and signals the deferred after 1.0 sec.

    ```
    def timer_function():
        deferred = Deferred()
        timeout = 1.0
        ioloop.add_timer(time.time() + timeout, lambda: deferred.ready('Done')
        return deferred
    ```

    Now you can use `timer_function` in Chain context:

    ```
    result = yield timer_function()
    ```
    """
    def __init__(self):
        super(Deferred, self).__init__()
        self.unbind()

    def bind(self, callback, errorback=None, on_done=None):
        self.callback = callback
        self.errorback = errorback

    def unbind(self):
        self.callback = None
        self.errorback = None

    def isBound(self):
        return any([self.callback, self.errorback])

    def ready(self, result=None):
        if not self.isBound():
            return

        if not isinstance(result, FutureResult):
            result = FutureResult(result)

        try:
            result = result.get()
            self.callback(result)
        except Exception as err:
            if self.errorback:
                self.errorback(err)


class ConcurrentWorker(object):
    def __init__(self, func, ioLoop=None, args=(), kwargs=None):
        self.func = func
        self.ioLoop = ioLoop or IOLoop.instance()
        self.args = args
        self.kwargs = kwargs or {}

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
        self._results = collections.deque(maxlen=1)
        self.__log = logging.getLogger(self.__module__ + '.' + self.__class__.__name__)

    def bind(self, callback, errorback=None, on_done=None):
        self.callback = callback
        self.errorback = errorback
        self.advance()

    def advance(self, value=None):
        try:
            result = self._next(value)
            future = self._wrapFuture(result)

            if result is not None:
                self.__log.debug('A - Binding future %s instead of %s', repr(future), repr(self._currentFuture))
                future.bind(self.advance, self.advance)
                if self._currentFuture:
                    self._currentFuture.unbind()
                self._currentFuture = future
        except StopIteration:
            self.__log.debug('A - StopIteration caught. Value - %s', repr(value))
            self.callback(value)
        except ChokeEvent as err:
            self.__log.debug('A - ChokeEvent caught. Value - %s', repr(value))
            self.errorback(err)
        except Exception as err:
            self.__log.debug('A - Error: %s', repr(err))
            if self._currentFuture and self._currentFuture.isBound():
                self._currentFuture.unbind()
            self.errorback(err)

    def _next(self, value):
        if isinstance(value, ChokeEvent):
            if self._results and self._results.pop() is None:
                result = self.coroutine.throw(ChokeEvent())
            else:
                result = self.coroutine.send(None)
        elif isinstance(value, Exception):
            result = self.coroutine.throw(value)
        else:
            result = self.coroutine.send(value)
        self._results.append(result)
        self.__log.debug('N - %s -> %s', repr(value), repr(result))
        return result

    def _wrapFuture(self, result):
        if isinstance(result, Future):
            future = result
        elif isinstance(result, Chain):
            deferred = Deferred()

            def cleanPending(r):
                deferred.ready(r)
                result.items[-1].pending = []
            result.then(cleanPending)
            future = deferred
        elif hasattr(result, 'add_done_callback'):
            # Meant to be tornado.concurrent._DummyFuture or python 3.3 concurrent.future.Future
            deferred = Deferred()

            def unwrapResult(result):
                try:
                    deferred.ready(result.result())
                except Exception as err:
                    deferred.ready(err)
            result.add_done_callback(unwrapResult)
            future = deferred
        elif isinstance(result, ConcurrentWorker):
            deferred = Deferred()
            result.runBackground(lambda r: deferred.ready(r))
            future = deferred
        else:
            future = PreparedFuture(result, ioLoop=self.ioLoop)
        self.__log.debug('W - %s -> %s', repr(result), repr(future))
        return future


class ChainItem(object):
    def __init__(self, func, ioLoop=None):
        self.func = func
        self.ioLoop = ioLoop or IOLoop.instance()
        self.next = None
        self.__log = logging.getLogger(self.__module__ + '.' + self.__class__.__name__)
        self.pending = []

    def setNext(self, item):
        self.next = item
        self.pending = []

    def execute(self, *args, **kwargs):
        try:
            self.__log.debug('%d: Executing "%s" with "%s" ...', id(self), self.func, repr(args))
            future = self.func(*args, **kwargs)
            self.__log.debug('%d: Execution done. Received - %s', id(self), repr(future))
            if isinstance(future, Future):
                pass
            elif isinstance(future, types.GeneratorType):
                future = GeneratorFutureMock(future, ioLoop=self.ioLoop)
            else:
                future = PreparedFuture(future, ioLoop=self.ioLoop)
            self.__log.debug('%d: Binding future %s', id(self), repr(future))
            future.bind(self.callback, self.errorback)
        except Exception as err:
            self.errorback(err)

    def callback(self, chunk):
        self.__log.debug('%d: ChainItem.callback - %s', id(self), repr(chunk))
        futureResult = FutureResult(chunk)
        if self.next:
            # Actually it does not matter if we invoke next chain item synchronously or via event loop.
            # But for convenience, let's do it asynchronously.
            self.ioLoop.add_callback(self.next.execute, futureResult)
        else:
            self.pending.append(futureResult)

    def errorback(self, error):
        self.callback(error)
        if not self.next and not (isinstance(error, ChokeEvent) or isinstance(error, StopIteration)):
            log.error(error, exc_info=True)


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
        self.__log = logging.getLogger(self.__module__ + '.' + self.__class__.__name__)
        self.items = []
        for func in functions:
            self.then(func)

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
        self.__log.debug('Adding function "%s" to the chain', repr(func))
        item = ChainItem(func, self.ioLoop)

        if len(self.items) == 0:
            self.__log.debug('Executing first chain item asynchronously - %s ...', repr(item))
            self.ioLoop.add_callback(item.execute)
        else:
            self.__log.debug('Coupling %s to %s', repr(item), repr(self.items[-1]))
            self.items[-1].setNext(item)

        self.items.append(item)
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
        return len(self._pending) > 0

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
            def fire():
                setattr(self, '__timeout', timeout)
                self.ioLoop.stop()
            self.ioLoop.add_timeout(time.time() + timeout, fire)

        isLoopRunning = self.ioLoop._running
        self.ioLoop.start()
        if isLoopRunning:
            self.ioLoop._running = True
            self.ioLoop._stopped = False
        self._removeTrackingLastResult()
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
        self._removeTrackingLastResult()

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

    @property
    def _pending(self):
        return self.items[-1].pending if self.items else []

    def _checkTimeout(self, timeout):
        if timeout is not None and timeout < 0.001:
            raise ValueError('timeout can not be less then 1 ms')

    def _trackLastResult(self):
        if not self._isTrackingForLastResult():
            def patch(func):
                def wrapper(*args, **kwargs):
                    try:
                        func(*args, **kwargs)
                    finally:
                        self.ioLoop.stop()
                return wrapper

            self.__callback = self.items[-1].callback
            self.items[-1].callback = patch(self.__callback)
            setattr(self, '__tracked', True)

    def _removeTrackingLastResult(self):
        if self._isTrackingForLastResult():
            self.items[-1].callback = self.__callback
            delattr(self, '__tracked')

    def _isTrackingForLastResult(self):
        return hasattr(self, '__tracked')

    def _getLastResult(self):
        if hasattr(self, '__timeout'):
            timeout = getattr(self, '__timeout')
            delattr(self, '__timeout')
            raise TimeoutError(timeout)

        assert len(self._pending) > 0

        lastResult = self._pending[0]
        if isinstance(lastResult.result, ChokeEvent):
            return lastResult.get()
        else:
            self._pending.pop(0)
            return lastResult.get()


def concurrent(func):
    """
    Wraps function or method, so it can be invoked concurrently by yielding in chain context.

    Program control will be returned to the yield statement once processing is done. Current implementation invokes
    function in separate thread.
    """
    def wrapper(*args, **kwargs):
        mock = ConcurrentWorker(func, ioLoop=None, args=args, kwargs=kwargs)
        return mock
    return wrapper


def source(func):
    """Marks function or method as source of chain context.

    It means, that the decorated function becomes the first function in the chain pipeline. As a result, there
    shouldn't be any parameter passed to that function (except `self` or `cls` for class methods).
    """
    def wrapper(*args, **kwargs):
        return Chain([lambda: func(*args, **kwargs)])
    return wrapper
