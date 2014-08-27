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

from tornado.gen import Return

from .io import CocaineIO
from ..decorators import coroutine
from .io import CocaineFuture


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
