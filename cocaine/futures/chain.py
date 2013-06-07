# coding=utf-8
__author__ = 'EvgenySafronov <division494@gmail.com>'


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

    def run(self, *args, **kwargs):
        try:
            future = self.func(*args, **kwargs)
            future.bind(self.on, self.error, self.done)
        except Exception as err:
            self.error(err)

    def on(self, chunk):
        if self.nextChain:
            result = Result(chunk)
            self.nextChain.run(result)

    def error(self, exception):
        self.on(exception)

    def done(self):
        self.on(None)


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


class FutureMock():
    def __init__(self, obj=None):
        """
        This class represents simple future wrapper on some result. It simple calls `callback` function with single
        `obj` parameter when `bind` method is called or `errorback` when some error occurred during `callback` invoking.
        """
        self.obj = obj

    def bind(self, callback, errorback, on_done=None):
        """
        NOTE: `on_done` callback is not used because it's not needed. You have to use this object only to store any
        data. Doneback hasn't any result, so it left here only for properly working `Chain` class.
        """
        try:
            callback(self.obj)
        except Exception as err:
            errorback(err)


class FutureCallableMock():
    """
    This class represents future wrapper over your asynchronous functions (i.e. tornado async callee).
    Once done, you must call `ready` method and pass the result to it.
    """
    def bind(self, callback, errorback, on_done=None):
        self.callback = callback
        self.errorback = errorback
        self.on_done = on_done

    def ready(self, result):
        try:
            self.callback(result)
            if self.on_done:
                self.on_done()
        except Exception as err:
            self.errorback(err)


def synchronous(func):
    def wrapper(*args, **kwargs):
        result = None
        try:
            result = func(*args, **kwargs)
        except Exception as err:
            result = err
        finally:
            return FutureMock(result)
    return wrapper


def asynchronousCallable(func):
    def wrapper(*args, **kwargs):
        future = FutureCallableMock()
        func(future, *args, **kwargs)
        return future
    return wrapper