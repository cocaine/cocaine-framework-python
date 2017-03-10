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

import datetime

from tornado import gen
from tornado.queues import Queue

from ..exceptions import ChokeEvent


class RequestError(Exception):
    def __init__(self, code, reason):
        super(RequestError, self).__init__()
        self.category, self.code = code
        self.reason = reason


class Stream(object):
    def __init__(self, raw_headers, header_table):
        self._queue = Queue()
        self._header_table = header_table
        self._current_headers = self._header_table.merge(raw_headers)

    @gen.coroutine
    def get(self, timeout=0):
        if timeout == 0:
            res, headers = yield self._queue.get()
        else:
            deadline = datetime.timedelta(seconds=timeout)
            res, headers = yield self._queue.get(deadline)

        self._current_headers = headers
        if isinstance(res, Exception):
            raise res
        else:
            raise gen.Return(res)

    def push(self, item, raw_headers):
        headers = self._header_table.merge(raw_headers)
        self._queue.put_nowait((item, headers))

    def done(self, raw_headers):
        headers = self._header_table.merge(raw_headers)
        return self._queue.put_nowait((ChokeEvent(), headers))

    def error(self, errnumber, reason, raw_headers):
        headers = self._header_table.merge(raw_headers)
        return self._queue.put_nowait((RequestError(errnumber, reason), headers))

    @property
    def headers(self):
        return self._current_headers


class RequestStream(Stream):
    def read(self, **kwargs):
        return self.get(**kwargs)

    def close(self, headers):
        return self.done(headers)
