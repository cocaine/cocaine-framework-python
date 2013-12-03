import functools
import threading
import time
import types
import logging

from tornado.ioloop import IOLoop

from cocaine.exceptions import ChokeEvent
from cocaine.asio.exceptions import TimeoutError, IllegalStateError
from cocaine.futures import Deferred


__author__ = 'Evgeny Safronov <division494@gmail.com>'


log = logging.getLogger(__name__)
engine_log = logging.getLogger('cocaine.engine')


class FutureResult(object):
    """
    Represents future result and provides methods to obtain this result, manipulate or reset.

    The result itself can be any object or exception. If some exception is stored, then it will be thrown after user
    invokes `get` method.

    .. note:: All methods in this class are reentrant.

    :ivar result: stored result
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

    def __str__(self):
        return 'FutureResult({0})'.format(self.result)


class PreparedFuture(Deferred):
    """Represents prepared future object with in advance known result.

    It is useful when you need to return already defined result from function and to use that function in some future
    context (like chain).

    Specified callback or errorback will be triggered on the next event loop turn after `bind` method is invoked.

    .. note:: While in engine context, you don't need to use it directly - if you return something from function that
              meant to be used as chain item, the result will be automatically wrapped with `PreparedFuture`.

    .. note:: All methods in this class are reentrant.

    :ivar result: stored result.
    """
    def __init__(self, result):
        super(PreparedFuture, self).__init__()
        self.result = result

    def bind(self, callback, errorback=None):
        callback(self.result)


class ConcurrentWorker(object):
    def __init__(self, func, io_loop=None, args=(), kwargs=None):
        self._func = func
        self._io_loop = io_loop or IOLoop.current()
        self._args = args
        self._kwargs = kwargs or {}

        self._worker = threading.Thread(target=self._run)
        self._worker.setDaemon(True)
        self._callback = None

    def _run(self):
        try:
            result = self._func(*self._args, **self._kwargs)
            self._callback(result)
        except Exception as err:
            self._callback(err)

    def execute(self, deferred):
        def dispatch_result(future):
            try:
                deferred.trigger(future.get())
            except Exception as err:
                deferred.error(err)
        self.run_background(dispatch_result)

    def run_background(self, callback):
        def on_done(result):
            self._io_loop.add_callback(lambda: callback(FutureResult(result)))
        self._callback = on_done
        self._worker.start()


class GeneratorFuture(Deferred):
    def __init__(self, g):
        super(GeneratorFuture, self).__init__()
        self._g = g
        self._current_deferred = None
        self._result, self._is_set = None, False

    def bind(self, callback, errorback=None):
        super(GeneratorFuture, self).bind(callback, errorback)
        self._advance()

    def _advance(self, value=None):
        try:
            result = self._next(value)
            future = self._wrap_result(result)

            if result is not None:
                if __debug__: log.debug('-- rebinding %s instead of %s', future, self._current_deferred)
                future.bind(self._advance, self._advance)
                if self._current_deferred:
                    self._current_deferred.unbind()
                self._current_deferred = future
        except StopIteration:
            if __debug__: log.debug('-- StopIteration: %s', value)
            self.trigger(value)
        except ChokeEvent as err:
            if __debug__: log.debug('-- ChokeEvent caught')
            self.error(err)
        except Exception as err:
            if __debug__: log.debug('-- Exception caught: %s', err)
            if self._current_deferred:
                self._current_deferred.unbind()
            self.error(err)

    def _next(self, value):
        if __debug__: log.debug('<-- "%s"', value if self._is_set and self._result is None else None)
        if isinstance(value, ChokeEvent):
            if self._result is None and self._is_set:
                result = self._g.throw(value)
            else:
                result = self._g.send(None)
        elif isinstance(value, Exception):
            result = self._g.throw(value)
        else:
            result = self._g.send(value)
        self._result, self._is_set = result, True
        if __debug__: log.debug('--> "%s"', result)

        if isinstance(value, ChokeEvent) and result is None:
            if __debug__: log.debug('-- exhausted generator detected')
            self._g.throw(value)
            raise value
        return result

    def _wrap_result(self, result):
        if isinstance(result, Deferred):
            future = result
        elif isinstance(result, Chain):
            deferred = Deferred()
            self._wrap_chain(result, deferred)
            future = deferred
        elif hasattr(result, 'add_done_callback'):
            # Meant to be tornado.concurrent._DummyFuture or python 3.3 concurrent.future.Future
            deferred = Deferred()
            self._wrap_python_future(result, deferred)
            future = deferred
        elif isinstance(result, ConcurrentWorker):
            deferred = Deferred()
            result.execute(deferred)
            future = deferred
        elif isinstance(result, All):
            deferred = Deferred()
            result.execute(deferred)
            future = deferred
        else:
            future = PreparedFuture(result)
        if __debug__: log.debug('== wrapping %s -> %s', result, future)
        return future

    def _wrap_chain(self, result, deferred):
        def cleanPending(r):
            try:
                deferred.trigger(r.get())
            except Exception as err:
                deferred.error(err)
            result.items[-1].pending = []
        result.then(cleanPending)

    def _wrap_python_future(self, result, deferred):
        def unwrapResult(result):
            try:
                deferred.trigger(result.result())
            except Exception as err:
                deferred.error(err)
        result.add_done_callback(unwrapResult)


def _track_mailbox(func):
    def wrapper(*args, **kwargs):
        try:
            log.debug('<~~ executing "%s" with "%s"', func, args)
            future = func(*args, **kwargs)
        except Exception as err:
            log.debug('~~> received: %s', err)
            raise
        else:
            log.debug('~~> received: %s', future)
            return future
    return wrapper


class ChainItem(object):
    def __init__(self, chain, func):
        self.chain = chain
        if __debug__:
            self.func = _track_mailbox(func)
        else:
            self.func = func
        self.next = None

    def couple(self, item):
        self.next = item

    def execute(self, *args, **kwargs):
        try:
            future = self.func(*args, **kwargs)
            if isinstance(future, Deferred):
                pass
            elif isinstance(future, types.GeneratorType):
                future = GeneratorFuture(future)
            else:
                future = PreparedFuture(future)
            future.bind(self.callback, self.errorback)
        except Exception as err:
            self.errorback(err)

    def callback(self, chunk):
        if __debug__: log.debug('~~ callback called with %s. Next chain item: %s', chunk, self.next)
        future = FutureResult(chunk)
        if self.next is not None:
            self.next.execute(future)
        else:
            self.chain.add_pending(future)

    def errorback(self, error):
        self.callback(error)
        if self.next is None and not (isinstance(error, ChokeEvent) or isinstance(error, StopIteration)):
            engine_log.debug('Uncaught exception reached end of the chain\n%s\n%s', 60 * '=', error, exc_info=True)


class Chain(object):
    """
    Represents pipeline of processing functions over chunks.

    This class represents chain of processing functions over incoming chunks. It manages creating chunk pipeline by
    binding them one-by-one.
    Incoming chunks will be processed separately in direct order.
    If some of processing function fails and raise an exception, it will be transported to the next chain item over and
    over again until it will be caught by `except` block or transferred to the event loop exception trap.

    There is also synchronous API provided, but it should be used only for scripting or tests.

    .. note:: All methods in this class are reentrant.
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
        self._io_loop = ioLoop or IOLoop.current()
        self.items = []
        for func in functions:
            self.then(func)

        self._pending = []
        self._pending_watcher = lambda: None
        self._raise_timeout = False
        self._timeout = 0.0

    # Private
    def add_pending(self, future):
        self._pending.append(future)
        self._pending_watcher()

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
        if __debug__: log.debug('~  adding function "%s" to the chain', func)
        item = ChainItem(self, func)

        if len(self.items) == 0:
            if __debug__: log.debug('~  executing first chain item asynchronously: %s ...', item)
            self._io_loop.add_callback(item.execute)
        else:
            if __debug__: log.debug('~  coupling %s with %s', item, self.items[-1])
            self.items[-1].couple(item)

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

        .. warning:: This is synchronous usage of chain object. Do not mix asynchronous and synchronous chain usage!

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
            def set_raise_timeout():
                self._raise_timeout = True
                self._timeout = timeout
                self._io_loop.stop()
            self._io_loop.add_timeout(time.time() + timeout, set_raise_timeout)

        ran = self._io_loop._running
        self._io_loop.start()
        if ran:
            self._io_loop._running = True
            self._io_loop._stopped = False
        self._removeTrackingLastResult()
        return self._getLastResult()

    def wait(self, timeout=None):
        """
        Waits chaining execution during some time or forever.

        This method provides you nice way to do asynchronous waiting future result from chain expression. Default
        implementation simply starts event loop, sets timeout condition and run chain expression. Event loop will be
        stopped after getting final chain result or after timeout expired. Unlike `get` method there will be no
        exception raised if timeout is occurred while chaining execution running.

        .. warning:: This is synchronous usage of chain object. Do not mix asynchronous and synchronous chain usage!

        :param timeout: Timeout in seconds after which event loop will be stopped. If timeout is not set (default) it
                        means forever waiting.
        :raises ValueError: If timeout is set and it is less than 1 ms.
        """
        self._checkTimeout(timeout)
        if self.hasPendingResult():
            return
        self._trackLastResult()
        if timeout:
            self._io_loop.add_timeout(time.time() + timeout, lambda: self._io_loop.stop())
        self._io_loop.start()
        self._removeTrackingLastResult()

    def __iter__(self):
        """
        Traits chain object as iterator. Note, that iterator can be used only once. Normally, you should not use this
        method directly - python uses it automatically in the `for` loop.

        .. warning:: This is synchronous usage of chain object. Do not mix asynchronous and synchronous chain usage!
        """
        return self

    def next(self):
        """
        Gets next chain result. Normally, you should not use this method directly - python uses it automatically in
        the `for` loop.

        .. warning:: This is synchronous usage of chain object. Do not mix asynchronous and synchronous chain usage!
        """
        try:
            return self.get()
        except ChokeEvent:
            raise StopIteration

    def _checkTimeout(self, timeout):
        if timeout is not None and timeout < 0.001:
            raise ValueError('timeout can not be less then 1 ms')

    def _trackLastResult(self):
        self._pending_watcher = self._io_loop.stop

    def _removeTrackingLastResult(self):
        self._pending_watcher = lambda: None

    def _getLastResult(self):
        if self._raise_timeout:
            timeout = self._timeout
            self._raise_timeout = False
            self._timeout = 0.0
            raise TimeoutError(timeout)

        assert len(self._pending) > 0

        head = self._pending[0]
        if isinstance(head.result, ChokeEvent):
            return head.get()
        else:
            self._pending.pop(0)
            return head.get()


def concurrent(func):
    """
    Wraps function or method, so it can be invoked concurrently by yielding in engine context.

    Program control will be returned to the yield statement once processing is done. Current implementation invokes
    function in separate thread.
    """
    def wrapper(*args, **kwargs):
        mock = ConcurrentWorker(func, io_loop=None, args=args, kwargs=kwargs)
        return mock
    return wrapper


def source(func):
    """Marks function or method as source of engine context.

    .. warning:: This decorator is deprecated. Use `engine.asynchronous` instead.
    """
    def wrapper(*args, **kwargs):
        return Chain([lambda: func(*args, **kwargs)])
    return wrapper


class All(object):
    """Represents yieldable object for asynchronous future grouping.

    This class provides ability to yield multiple yieldable objects in engine context. Program control returns after
    all of them completed. Future results will be placed in the list in original order.

    Typical usage::

        from cocaine.services import Service
        from cocaine.futures import chain
        @engine.asynchronous
        def func():
            r1, r2 = yield chain.All([s1.execute(), s2.execute()])
            print(r1, r2)
        s1 = Service('s1')
        s2 = Service('s2')
        func()

    If you have specified deferred, you can invoke `execute` method and pass that deferred to it. This will have the
    same effect as yielding.

    .. note:: You can yield this class's objects only in engine context and only once. Think about this class as some
              kind of single-shot.
    .. note:: All methods in this class are thread-safe.
    """
    def __init__(self, futures):
        self._futures = futures
        self._results = [None] * len(futures)
        self._activated = False
        self._counter = len(futures)
        self._lock = threading.Lock()

    def execute(self, deferred):
        """Executes asynchronous grouped future invocation and binds `deferred` to the completion event.

        :param deferred: deferred, which will be invoked after all of futures are completed.
        """
        with self._lock:
            if self._activated:
                raise IllegalStateError('already activated')

            for id_, future in enumerate(self._futures):
                wait = functools.partial(self._waitFuture, future)
                collect = functools.partial(self._collect, id_, deferred)
                Chain([wait, collect])

    def _waitFuture(self, future):
        first = yield future
        chunks = []
        try:
            while True:
                other = yield
                chunks.append(other)
        except ChokeEvent:
            pass

        if chunks:
            chunks.insert(0, first)
            yield chunks
        else:
            yield first

    def _collect(self, id_, deferred, result):
        try:
            self._results[id_] = result.get()
            self._counter -= 1
            if self._counter == 0:
                deferred.trigger(self._results)
        except Exception as err:
            deferred.error(err)
