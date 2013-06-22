from __future__ import absolute_import
from threading import Thread
import logging
import time
import types
from tornado.ioloop import IOLoop
from cocaine.futures import Future
from cocaine.exceptions import TimeoutError

__author__ = 'EvgenySafronov <division494@gmail.com>'


log = logging.getLogger(__name__)


class Result(object):
    """
    Simple object which main aim is to store some result and to provide 'get' method to unpack the result.
    The result can be any object or exception. If it is an exception then it will be thrown after user calls 'get'.
    """
    def __init__(self, obj):
        self.obj = obj

    def get(self):
        if isinstance(self.obj, Exception):
            raise self.obj
        else:
            return self.obj


class Chain(object):
    def __init__(self, func, nextChain=None):
        """
        This class represents chain element by storing some function and invoking it as is turn comes.
        If method `run` is called it invokes `func` with specified arguments and receives its result or catches an
        exception
        """
        self.func = func
        self.nextChain = nextChain
        self.finished = False

    def run(self, *args, **kwargs):
        try:
            result = self.func(*args, **kwargs)
            if isinstance(result, Future):
                future = result
            elif isinstance(result, types.GeneratorType):
                future = GeneratorFutureMock(result)
            else:
                future = FutureMock(result)
            future.bind(self.on, self.error, self.done)
        except Exception as err:
            self.error(err)

    def on(self, chunk):
        if self.nextChain and not self.finished:
            result = Result(chunk)
            self.nextChain.run(result)

    def error(self, exception):
        if not self.finished:
            self.on(exception)
            self.finished = True

    def done(self):
        if not self.finished:
            self.on(None)
            self.finished = True


class ChainFactory():
    """
    This class - is some syntax sugar over `Chain` object chains. Instead of writing code like this:
        c1 = Chain(f1, Chain(f2, Chain(f3, ...Chain(fn)))...).run()
    you can write:
        ChainFactory().then(f1).then(f2).then(f3) ... then(fn).run()
    and this looks like more prettier.
    """
    def __init__(self, functions=None):
        if not functions:
            functions = []

        self.chains = []
        for func in functions:
            self.then(func)

    def then(self, func):
        self.chains.append(Chain(func))
        return self

    def run(self):
        for i in xrange(len(self.chains) - 1):
            self.chains[i].nextChain = self.chains[i + 1]
        self.chains[0].run()

    def get(self, timeout=None):
        """
        This method is like syntax sugar over asynchronous receiving future result from chain expression. It simply
        starts event loop, sets timeout condition and run chain expression. Event loop will be stopped after getting
        final chain result or after timeout expired.

        :param timeout: Timeout in seconds after which TimeoutError will be raised. If timeout is not set (default) it
                        means forever waiting.
        :raises ValueError: If timeout is set and it is less than 1 ms.
        :raises TimeoutError: If timeout expired.
        """
        if timeout is not None and timeout < 0.001:
            raise ValueError('Timeout cannot be less than 1 ms')

        loop = IOLoop.instance()
        def startNestedEventLoop(result):
            try:
                startNestedEventLoop.result = result.get()
            except Exception as err:
                startNestedEventLoop.result = err
            finally:
                startNestedEventLoop.resultIsSet = True
                loop.stop()

        def stopNestedEventLoop():
            stopNestedEventLoop.raiseTimeoutError = True
            loop.stop()

        startNestedEventLoop.resultIsSet = False
        startNestedEventLoop.result = None
        stopNestedEventLoop.raiseTimeoutError = False
        self.then(startNestedEventLoop).run()
        if timeout is not None:
            loop.add_timeout(time.time() + timeout, stopNestedEventLoop)
        loop.start()

        if stopNestedEventLoop.raiseTimeoutError and not startNestedEventLoop.resultIsSet:
            raise TimeoutError('Timeout')
        if isinstance(startNestedEventLoop.result, Exception):
            raise startNestedEventLoop.result
        return startNestedEventLoop.result


class FutureMock(Future):
    def __init__(self, obj=None):
        """
        This class represents simple future wrapper on some result. It simple deferredly calls `callback` function with
        single `obj` parameter when `bind` method is called or `errorback` when some error occurred during `callback`
        invoking.
        """
        super(FutureMock, self).__init__()
        self.obj = obj

    def bind(self, callback, errorback=None, on_done=None):
        """
        NOTE: `on_done` callback is not used because it's not needed. You have to use this object only to store any
        data. Doneback hasn't any result, so it left here only for having the same signature with Future.bind method
        """
        try:
            self.invokeAsynchronously(lambda: callback(self.obj))
        except Exception as err:
            if errorback:
                self.invokeAsynchronously(lambda: errorback(err))

    def invokeAsynchronously(self, callback):
        IOLoop.instance().add_timeout(time.time(), lambda: callback())


class GeneratorFutureMock(Future):
    """
    This class represents future wrapper over coroutine function as chain item.
    """
    def __init__(self, obj=None):
        super(GeneratorFutureMock, self).__init__()
        self.obj = obj
        self.counter = 0

    def bind(self, callback, errorback=None, on_done=None):
        self.cb = callback
        self.eb = errorback
        self.advance()

    def advance(self, value=None):
        try:
            log.debug('Advance({0}) - {1}'.format(self.counter, value))
            self.counter += 1
            result = self.nextStep(value)
            future = self.wrapResult(result)
            if result is not None:
                future.bind(self.advance, self.advance)
            log.debug('Advance got: {0} -> {1}'.format(result, future))
        except StopIteration:
            log.debug('StopIteration')
            self.cb(value)
        except Exception as err:
            log.error(err)
            if self.eb:
                self.eb(err)

    def nextStep(self, value):
        if isinstance(value, Exception):
            result = self.obj.throw(value)
            print self.obj
        else:
            result = self.obj.send(value)
        return result

    def wrapResult(self, result):
        if isinstance(result, Future):
            future = result
        elif isinstance(result, ChainFactory):
            chainFuture = FutureCallableMock()
            result.then(lambda r: chainFuture.ready(r.get()))
            result.run()
            future = chainFuture
        elif isinstance(result, ThreadWorker):
            threadFuture = FutureCallableMock()
            result.runBackground(lambda r: threadFuture.ready(r))
            future = threadFuture
        else:
            future = FutureMock(result)
        return future


class FutureCallableMock(Future):
    """
    This class represents future wrapper over your asynchronous functions (i.e. tornado async callee).
    Once done, you must call `ready` method and pass the result to it.

    WARNING: `on_done` function is not used. Do not pass it!
    """
    def bind(self, callback, errorback=None, on_done=None):
        self.callback = callback
        self.errorback = errorback
        self.on_done = on_done

    def ready(self, result):
        try:
            self.callback(result)
        except Exception as err:
            if self.errorback:
                self.errorback(err)


class ThreadWorker(object):
    def __init__(self, func, *args, **kwargs):
        self.func = func
        self.args = args
        self.kwargs = kwargs
        self.thread = Thread(target=self._run)
        self.thread.setDaemon(True)
        self.callback = None

    def _run(self):
        try:
            result = self.func(*self.args, **self.kwargs)
            self.callback(result)
        except Exception as err:
            self.callback(err)

    def runBackground(self, callback):
        def onDone(result):
            IOLoop.instance().add_callback(lambda: callback(result))
        self.callback = onDone
        self.thread.start()


def asynchronousCallable(func):
    def wrapper(*args, **kwargs):
        future = FutureCallableMock()
        func(future, *args, **kwargs)
        return future
    return wrapper


def threaded(func):
    def wrapper(*args, **kwargs):
        mock = ThreadWorker(func, *args, **kwargs)
        return mock
    return wrapper