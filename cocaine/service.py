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

import collections
import itertools
import logging
import sys
import threading
import types

try:
    import Queue
except ImportError:  # pragma: no cover
    import queue as Queue

import concurrent
import msgpack
import tornado.concurrent


# Make it thread-safe
class CocaineFuture(tornado.concurrent.Future):
    def result(self, timeout=None):
        if not self.done():
            foo = concurrent.futures.Future()
            chain_future(self, foo)
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
# End of Monkey patch

from tornado.concurrent import chain_future
from tornado.concurrent import TracebackFuture
from tornado.ioloop import IOLoop
# from tornado.log import LogFormatter
from tornado.tcpclient import TCPClient
from tornado.gen import Return, Runner
from tornado import stack_context

from cocaine.api import API

log = logging.getLogger("tornado")
# sh = logging.StreamHandler()
# sh.setFormatter(LogFormatter())
# log.setLevel(logging.DEBUG)
# log.addHandler(sh)


class CocaineTCPClient(TCPClient):
    def __init__(self, *args, **kwargs):
        super(CocaineTCPClient, self).__init__(*args, **kwargs)

    def connect(self, host, port):
        result_future = CocaineFuture()

        def migrate_context():
            connection_future = super(CocaineTCPClient, self).connect(host, port)
            chain_future(connection_future, result_future)

        # post this to handle connection of IOStream
        # in Cocaine IO thread
        self.io_loop.post(migrate_context)
        return result_future


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


class QueueEmpty(Exception):
    pass


class QueueFull(Exception):
    pass


class AsyncQueue(object):
    """
    Inspired by asyncio.Queue
    """

    def __init__(self, maxsize=0, io_loop=None):
        self._loop = io_loop or CocaineIO.instance()
        self._maxsize = maxsize

        # Futures.
        self._getters = collections.deque()
        # Pairs of (item, Future).
        self._putters = collections.deque()
        self._init(maxsize)

    def _init(self, maxsize):
        self._queue = collections.deque()

    def _get(self):
        return self._queue.popleft()

    def _put(self, item):
        self._queue.append(item)

    def _consume_done_getters(self):
        # Delete waiters at the head of the get() queue who've timed out.
        while self._getters and self._getters[0].done():
            self._getters.popleft()

    def _consume_done_putters(self):
        # Delete waiters at the head of the put() queue who've timed out.
        while self._putters and self._putters[0][1].done():
            self._putters.popleft()

    def qsize(self):
        """Number of items in the queue."""
        return len(self._queue)

    @property
    def maxsize(self):
        """Number of items allowed in the queue."""
        return self._maxsize

    def empty(self):
        """Return True if the queue is empty, False otherwise."""
        return not self._queue

    def full(self):
        """Return True if there are maxsize items in the queue.

        Note: if the Queue was initialized with maxsize=0 (the default),
        then full() is never True.
        """
        if self._maxsize <= 0:
            return False
        else:
            return self.qsize() >= self._maxsize

    @coroutine
    def put(self, item):
        """Put an item into the queue.

        If you yield From(put()), wait until a free slot is available
        before adding item.
        """
        self._consume_done_getters()
        if self._getters:
            assert not self._queue, (
                'queue non-empty, why are getters waiting?')

            getter = self._getters.popleft()

            # Use _put and _get instead of passing item straight to getter, in
            # case a subclass has logic that must run (e.g. JoinableQueue).
            self._put(item)
            getter.set_result(self._get())

        elif self._maxsize > 0 and self._maxsize <= self.qsize():
            waiter = CocaineFuture()

            self._putters.append((item, waiter))
            yield waiter

        else:
            self._put(item)

    def put_nowait(self, item):
        """Put an item into the queue without blocking.

        If no free slot is immediately available, raise QueueFull.
        """
        self._consume_done_getters()
        if self._getters:
            assert not self._queue, (
                'queue non-empty, why are getters waiting?')

            getter = self._getters.popleft()

            # Use _put and _get instead of passing item straight to getter, in
            # case a subclass has logic that must run (e.g. JoinableQueue).
            self._put(item)
            getter.set_result(self._get())

        elif self._maxsize > 0 and self._maxsize <= self.qsize():
            raise QueueFull
        else:
            self._put(item)

    @coroutine
    def get(self):
        """Remove and return an item from the queue.

        If you yield From(get()), wait until a item is available.
        """
        self._consume_done_putters()
        if self._putters:
            assert self.full(), 'queue not full, why are putters waiting?'
            item, putter = self._putters.popleft()
            self._put(item)

            # When a getter runs and frees up a slot so this putter can
            # run, we need to defer the put for a tick to ensure that
            # getters and putters alternate perfectly. See
            # ChannelTest.test_wait.
            self._loop.call_soon(putter._set_result_unless_cancelled, None)

            raise Return(self._get())

        elif self.qsize():
            raise Return(self._get())
        else:
            waiter = CocaineFuture()

            self._getters.append(waiter)
            result = yield waiter
            raise Return(result)

    def get_nowait(self):
        """Remove and return an item from the queue.

        Return an item if one is immediately available, else raise QueueEmpty.
        """
        self._consume_done_putters()
        if self._putters:
            assert self.full(), 'queue not full, why are putters waiting?'
            item, putter = self._putters.popleft()
            self._put(item)
            # Wake putter on next tick.
            putter.set_result(None)

            return self._get()

        elif self.qsize():
            return self._get()
        else:
            raise QueueEmpty


class ChokeEvent(Exception):
    pass


class ServiceError(Exception):
    def __init__(self, errnumber, reason):
        self.errno = errnumber
        self.reason = reason
        super(Exception, self).__init__("%s %s" % (self.errno, self.reason))


class InvalidApiVerison(ServiceError):
    def __init__(self, name, expected_version, got_version):
        message = "service `%s`invalid API version: expected `%d`, got `%d`" % (name, expected_version, got_version)
        super(InvalidApiVerison, self).__init__(-999, message)


class InvalidMessageType(ServiceError):
    pass


def StreamedProtocol(name, payload):
    if name == "write":
        return payload
    elif name == "error":
        return ServiceError(*payload)
    elif name == "close":
        return ChokeEvent()


class Rx(object):
    def __init__(self, rx_tree):
        self._queue = AsyncQueue()
        self._done = False
        self.rx_tree = rx_tree

    @coroutine
    def get(self, timeout=0, protocol=StreamedProtocol):
        if self._done and self._queue.empty():
            raise ChokeEvent()

        name, payload = yield self._queue.get()
        res = protocol(name, payload)
        if isinstance(res, Exception):
            raise res
        else:
            raise Return(res)

    def done(self):
        self._done = True

    # def error(self, errnumber, reason):
    #     return self._queue.put_nowait(ServiceError(errnumber, reason))

    def push(self, msg_type, payload):
        dispatch = self.rx_tree.get(msg_type)
        log.debug("dispatch %s", dispatch)
        if dispatch is None:
            raise InvalidMessageType(-998, "unexpected message type %s" % msg_type)
        name, rx, _ = dispatch
        log.debug("name `%s` rx `%s` %s", name, rx, _)
        self._queue.put_nowait((name, payload))
        if rx == {}:  # last transition
            self.done()
        elif rx is not None:  # recursive transition
            self.rx_tree = rx


class Tx(object):
    def __init__(self, tx_tree, pipe, session_id):
        self.tx_tree = tx_tree
        self.session_id = session_id
        self.pipe = pipe

    @coroutine
    def _invoke(self, method_name, *args, **kwargs):
        log.debug("_invoke has been called %s %s", str(args), str(kwargs))
        for method_id, (method, tx_tree, rx_tree) in self.tx_tree.iteritems():
            if method == method_name:
                log.debug("method `%s` has been found in API map", method_name)
                self.pipe.write(msgpack.packb([self.session_id, method_id, args]))
                raise Return(None)
        raise AttributeError("method_name")

    def __getattr__(self, name):
        def on_getattr(*args, **kwargs):
            return self._invoke(name, *args, **kwargs)
        return on_getattr


class BaseService(object):
    def __init__(self, name, host='localhost', port=10053, loop=None):
        self.loop = loop or CocaineIO.instance()
        self.host = host
        self.port = port
        self.name = name

        self._extra = {'service': self.name,
                       'id': id(self)}
        self.log = logging.LoggerAdapter(log, self._extra)

        self.sessions = {}
        self.counter = itertools.count(1)
        self.api = {}

        self._lock = threading.Lock()

        # wrap into separate class
        self.pipe = None
        self.buffer = msgpack.Unpacker()

    @coroutine
    def connect(self):
        if not self._connected:
            with self._lock:
                if not self._connected:
                    self.pipe = yield CocaineTCPClient(io_loop=self.loop).connect(self.host,
                                                                                  self.port)
                    self.pipe.read_until_close(callback=self.on_close,
                                               streaming_callback=self.on_read)
                    self.log.debug("connection has been established successfully")

    def disconnect(self):
        with self._lock:
            if self.pipe is not None:
                self.pipe.close()

    def on_close(self, *args):
        self.log.info("Pipe has been closed %s", args)
        with self._lock:
            self.pipe = None
        # ToDo: push error into current sessions

    def on_read(self, read_bytes):
        self.log.info("Pipe: read %s", read_bytes)
        self.buffer.feed(read_bytes)
        for msg in self.buffer:
            self.log.info("Unpacked: %s", msg)
            try:
                session, message_type, payload = msg
                self.log.debug("%s, %d, %s", session, message_type, payload)
            except Exception as err:
                self.log.error("malformed message: `%s` %s", err, str(msg))
                continue

            rx = self.sessions.get(session)
            if rx is None:
                self.log.warning("unknown session number: `%d`", session)
                continue

            rx.push(message_type, payload)

    @coroutine
    def _invoke(self, method_name, *args, **kwargs):
        self.log.debug("_invoke has been called %s %s", str(args), str(kwargs))
        yield self.connect()
        self.log.debug("%s", self.api)
        for method_id, (method, tx_tree, rx_tree) in self.api.iteritems():
            if method == method_name:
                self.log.debug("method `%s` has been found in API map", method_name)
                counter = self.counter.next()
                self.log.debug('sending message: %s', [counter, method_id, args])
                self.pipe.write(msgpack.packb([counter, method_id, args]))
                self.log.debug("RX TREE %s", rx_tree)
                self.log.debug("TX TREE %s", tx_tree)

                rx = Rx(rx_tree)
                tx = Tx(tx_tree, self.pipe, counter)
                self.sessions[counter] = rx
                raise Return((rx, tx))
        raise AttributeError("method_name")

    @property
    def _connected(self):
        return self.pipe is not None

    def __getattr__(self, name):
        def on_getattr(*args, **kwargs):
            return self._invoke(name, *args, **kwargs)
        return on_getattr


class Locator(BaseService):
    def __init__(self, host="localhost", port=10053, loop=None):
        super(Locator, self).__init__(name="locator",
                                      host=host, port=port, loop=loop)
        self.api = API.Locator


class Service(BaseService):
    def __init__(self, name, host="localhost", port=10053, version=0, loop=None):
        super(Service, self).__init__(name=name, loop=loop)
        self.locator = Locator(host=host, port=port, loop=loop)
        self.api = {}
        self.host = None
        self.port = None
        self.version = version

    @coroutine
    def connect(self):
        self.log.debug("checking if service connected", extra=self._extra)
        if self._connected:
            log.debug("already connected", extra=self._extra)
            return

        self.log.info("resolving ...", extra=self._extra)
        rx, _ = yield self.locator.resolve(self.name)
        (self.host, self.port), version, self.api = yield rx.get()
        log.info("successfully resolved", extra=self._extra)

        # Version compatibility should be checked here.
        if not (self.version == 0 or version == self.version):
            # raise Exception("wrong service `%s` API version %d, %d is needed" %
            #                 (self.name, version, self.version))
            raise InvalidApiVerison(self.name, version, self.version)
        yield super(Service, self).connect()
