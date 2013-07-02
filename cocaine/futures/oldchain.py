# class Result(object):
#     """
#     Simple object which main aim is to store some result and to provide 'get' method to unpack the result.
#     The result can be any object or exception. If it is an exception then it will be thrown after user calls 'get'.
#
# class Chain(object):
#     def __init__(self, func, nextChain=None):
#         """
#         This class represents chain element by storing some function and invoking it as is turn comes.
#         If method `run` is called it invokes `func` with specified arguments and receives its result or catches an
#         exception
#         """
#
# class ChainFactory():
#     """
#     This class - is some syntax sugar over `Chain` object chains. Instead of writing code like this:
#         `c1 = Chain(f1, Chain(f2, Chain(f3, ...Chain(fn)))...).run()`
#     you can write:
#         `ChainFactory().then(f1).then(f2).then(f3) ... then(fn).run()`
#     and this looks like more prettier.
#     """
#
#     def get(self, timeout=None):
#         """
#         Returns result of chaining execution. If chain haven't been completed after `timeout` seconds, there will be
#         exception raised.
#
#         This method is like syntax sugar over asynchronous receiving future result from chain expression. It simply
#         starts event loop, sets timeout condition and run chain expression. Event loop will be stopped after getting
#         final chain result or after timeout expired.
#
#         :param timeout: Timeout in seconds after which TimeoutError will be raised. If timeout is not set (default) it
#                         means forever waiting.
#         :raises ValueError: If timeout is set and it is less than 1 ms.
#         :raises TimeoutError: If timeout expired.
#         """
#
#     def wait(self, timeout=None):
#         """
#         Waits chaining execution during some time or forever.
#
#         This method provides you nice way to do asynchronous waiting future result from chain expression. It simply
#         starts event loop, sets timeout condition and run chain expression. Event loop will be stopped after getting
#         final chain result or after timeout expired. Unlike `get` method there will be no exception raised if timeout
#         is occurred while chaining execution running.
#
#         :param timeout: Timeout in seconds after which event loop will be stopped. If timeout is not set (default) it
#                         means forever waiting.
#         :raises ValueError: If timeout is set and it is less than 1 ms.
#         """
#
# class FutureMock(Future):
#     def __init__(self, obj=None):
#         """
#         This class represents simple future wrapper on some result. It simple deferredly calls `callback` function with
#         single `obj` parameter when `bind` method is called or `errorback` when some error occurred during `callback`
#         invoking.
#         """
#
#     def bind(self, callback, errorback=None, on_done=None):
#         """
#         NOTE: `on_done` callback is not used because it's not needed. You have to use this object only to store any
#         data. Doneback hasn't any result, so it left here only for having the same signature with Future.bind method
#         """
#
# class GeneratorFutureMock(Future):
#     """
#     This class represents future wrapper over coroutine function as chain item.
#     """
#
# class FutureCallableMock(Future):
#     """
#     This class represents future wrapper over your asynchronous functions (i.e. tornado async callee).
#     Once done, you must call `ready` method and pass the result to it.
#
#     WARNING: `on_done` function is not used. Do not pass it!
#     """
#
# class ThreadWorker(object):
#     def __init__(self, func, *args, **kwargs):
#         self.func = func
#         self.args = args
#         self.kwargs = kwargs
#         self.thread = Thread(target=self._run)
#         self.thread.setDaemon(True)
#         self.callback = None
#
#     def _run(self):
#         try:
#             result = self.func(*self.args, **self.kwargs)
#             self.callback(result)
#         except Exception as err:
#             self.callback(err)
#
#     def runBackground(self, callback):
#         def onDone(result):
#             IOLoop.instance().add_callback(lambda: callback(result))
#         self.callback = onDone
#         self.thread.start()
#
#
# def asynchronousCallable(func):
#     def wrapper(*args, **kwargs):
#         future = FutureCallableMock()
#         func(future, *args, **kwargs)
#         return future
#     return wrapper
#
#
# def threaded(func):
#     def wrapper(*args, **kwargs):
#         mock = ThreadWorker(func, *args, **kwargs)
#         return mock
#     return wrapper