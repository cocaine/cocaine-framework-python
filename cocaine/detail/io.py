#
#    Copyright (c) 2012+ Anton Tyurin <noxiouz@yandex.ru>
#    Copyright (c) 2013+ Evgeny Safronov <division494@gmail.com>
#    Copyright (c) 2011-2014 Other contributors as noted in the AUTHORS file.
#
#    This file is part of Cocaine.
#
#    Cocaine is free software; you can redistribute it and/or modify
#    it under the terms of the GNU Lesser General Public License as published by
#    the Free Software Foundation; either version 3 of the License, or
#    (at your option) any later version.
#
#    Cocaine is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#    GNU Lesser General Public License for more details.
#
#    You should have received a copy of the GNU Lesser General Public License
#    along with this program. If not, see <http://www.gnu.org/licenses/>.
#

import sys
import types
import threading

try:
    import Queue
except ImportError:  # pragma: no cover
    import queue as Queue

from tornado.ioloop import IOLoop
from tornado.ioloop import PeriodicCallback

import concurrent
import tornado.concurrent


# Make it thread-safe
class CocaineFuture(tornado.concurrent.Future):
    def result(self, timeout=None):
        if not self.done():
            foo = concurrent.futures.Future()
            tornado.concurrent.chain_future(self, foo)
            return foo.result(timeout)
        else:
            return super(CocaineFuture, self).result(timeout)

    def wait(self, timeout=None):
        return self.result(timeout)


# Monkey patch
def CocaineMonkeyPatch():
    import tornado.concurrent
    tornado.concurrent.TracebackFuture = CocaineFuture
    tornado.concurrent.Future = CocaineFuture

CocaineMonkeyPatch()
# Enf of monkey patch

from tornado.concurrent import TracebackFuture
from tornado.gen import Return
from tornado.gen import Runner
from tornado import stack_context


def coroutine(func):
    def wrapper(*args, **kwargs):
        future = TracebackFuture()
        try:
            result = func(*args, **kwargs)
        except (Return, StopIteration) as e:
            result = getattr(e, 'value', None)
        except Exception:
            future.set_exc_info(sys.exc_info())
            return future
        else:
            if isinstance(result, types.GeneratorType):
                # Inline the first iteration of Runner.run.  This lets us
                # avoid the cost of creating a Runner when the coroutine
                # never actually yields, which in turn allows us to
                # use "optional" coroutines in critical path code without
                # performance penalty for the synchronous case.
                try:
                    orig_stack_contexts = stack_context._state.contexts
                    yielded = next(result)
                    if stack_context._state.contexts is not orig_stack_contexts:
                        yielded = TracebackFuture()
                        yielded.set_exception(
                            stack_context.StackContextInconsistentError(
                                'stack_context inconsistency (probably caused '
                                'by yield within a "with StackContext" block)'))
                except (StopIteration, Return) as e:
                    future.set_result(getattr(e, 'value', None))
                except Exception:
                    future.set_exc_info(sys.exc_info())
                else:
                    # post runner into Cocaine ioloop
                    CocaineIO.instance().post(Runner, result, future, yielded)
                return future
        future.set_result(result)
        return future
    return wrapper


class CocaineIO(object):
    _instance_lock = threading.Lock()

    def __init__(self, io_loop, thread):
        self._io_loop = io_loop
        self._thread = thread

    def __getattr__(self, name):
        return getattr(self._io_loop, name)

    @staticmethod
    def instance():
        if not hasattr(CocaineIO, "_instance"):
            with CocaineIO._instance_lock:
                if not hasattr(CocaineIO, "_instance"):
                    q = Queue.Queue(1)

                    def _initialize(queue):
                        result = None
                        try:
                            # create new IOLoop in the thread
                            io_loop = IOLoop()
                            # make it default for that thread
                            io_loop.make_current()
                            result = io_loop
                            io_loop.add_callback(queue.put, result)
                            io_loop.start()
                        except Exception as err:  # pragma: no cover
                            result = err
                        finally:  # pragma: no cover
                            queue.put(result)

                    t = threading.Thread(target=_initialize,
                                         args=(q,),
                                         name="cocaineio_thread")
                    t.daemon = True
                    t.start()
                    result = q.get(True, 1)

                    if isinstance(result, IOLoop):
                        CocaineIO._instance = CocaineIO(result, t)
                    elif isinstance(result, Exception):  # pragma: no cover
                        raise result
                    else:  # pragma: no cover
                        raise Exception("Initialization error")
        return CocaineIO._instance

    def stop(self):  # pragma: no cover
        self.post(self._io_loop.stop)

    def post(self, callback, *args, **kwargs):
        self._io_loop.add_callback(callback, *args, **kwargs)

    def add_future(self, future, callback):
        self.post(self._io_loop.add_future, future, callback)


class Timer(PeriodicCallback):
    def __init__(self, callback, callback_time, io_loop):
        super(Timer, self).__init__(callback, callback_time * 1000, io_loop or CocaineIO.instance())
