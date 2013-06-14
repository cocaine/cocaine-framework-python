from __future__ import absolute_import
import logging
import time
import types
from tornado.ioloop import IOLoop
from cocaine.futures import Future

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
        exception. The function `func` MUST return the `Future` object with `bind` method with three callbacks defined.
        If it is not - use `synchronous` and `asynchronousCallable` decorators or `FutureMock` and `FutureCallableMock`
        classes directly.
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
    def __init__(self):
        self.chains = []

    def then(self, func):
        self.chains.append(Chain(func))
        return self

    def run(self):
        for i in xrange(len(self.chains) - 1):
            self.chains[i].nextChain = self.chains[i + 1]
        self.chains[0].run()


class FutureMock(Future):
    def __init__(self, obj=None):
        """
        This class represents simple future wrapper on some result. It simple calls `callback` function with single
        `obj` parameter when `bind` method is called or `errorback` when some error occurred during `callback` invoking.
        """
        super(FutureMock, self).__init__()
        self.obj = obj

    def bind(self, callback, errorback=None, on_done=None):
        """
        NOTE: `on_done` callback is not used because it's not needed. You have to use this object only to store any
        data. Doneback hasn't any result, so it left here only for properly working `Chain` class.
        """
        try:
            self.invokeAsynchronously(lambda: callback(self.obj))
        except Exception as err:
            if errorback:
                self.invokeAsynchronously(lambda: errorback(err))

    def invokeAsynchronously(self, callback):
        IOLoop.instance().add_timeout(time.time(), lambda: callback())



class GeneratorFutureMock(Future):
    def __init__(self, obj=None):
        super(GeneratorFutureMock, self).__init__()
        self.obj = obj
        self.counter = 0

    def bind(self, callback, errorback=None, on_done=None):
        self.cb = callback
        self.advance()

    def advance(self, value=None):
        try:
            log.debug('Advance({0}) - {1}'.format(self.counter, value))
            self.counter += 1
            result = self.nextStep(value)
            future = self.wrapResult(result)
            if result:
                future.bind(self.advance, self.advance)
            log.debug('Advance got: {0} -> {1}'.format(result, future))
        except StopIteration:
            log.debug('StopIteration')
            self.cb(value)
        except Exception as err:
            log.error(err)

    def nextStep(self, value):
        if isinstance(value, Exception):
            result = self.obj.throw(value)
        else:
            result = self.obj.send(value)
        return result

    def wrapResult(self, result):
        if isinstance(result, Future):
            future = result
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


def asynchronousCallable(func):
    def wrapper(*args, **kwargs):
        future = FutureCallableMock()
        func(future, *args, **kwargs)
        return future
    return wrapper