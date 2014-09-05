#
#    Copyright (c) 2014+ Anton Tyurin <noxiouz@yandex.ru>
#    Copyright (c) 2014+ Evgeny Safronov <division494@gmail.com>
#    Copyright (c) 2011-2014 Other contributors as noted in the AUTHORS file.
#
#    This file is part of Cocaine.
#
#    Cocaine is free software; you can redistribute it and/or modify
#    it under the terms of the GNU Lesser General Public License as published
#    by the Free Software Foundation; either version 3 of the License, or
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

from ..detail.asyncqueue import AsyncQueue
from ..decorators import coroutine

from tornado import gen


class ChokeEvent(Exception):
    pass


class ServiceError(Exception):
    def __init__(self, errnumber, reason):
        self.errno = errnumber
        self.reason = reason
        super(Exception, self).__init__("%s %s" % (self.errno, self.reason))


class Stream(object):
    def __init__(self):
        self._queue = AsyncQueue()
        self._done = False

    @coroutine
    def get(self, timeout=0):
        # if timeout > 0:
        #     res = yield asyncio.wait_for(self._queue.get(), timeout)
        # else:
        res = yield self._queue.get()

        if isinstance(res, Exception):
            raise res
        else:
            raise gen.Return(res)

    def push(self, item):
        self._queue.put_nowait(item)

    def done(self):
        return self._queue.put_nowait(ChokeEvent())

    def error(self, errnumber, reason):
        return self._queue.put_nowait(ServiceError(errnumber, reason))


class RequestStream(Stream):
    def read(self, **kwargs):
        return self.get(**kwargs)

    def close(self):
        return self.done()
