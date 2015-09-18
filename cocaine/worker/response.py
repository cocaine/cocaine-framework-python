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

import traceback

from ..common import CocaineErrno
from ..common import ErrorCategory
from ..detail.util import valid_chunk
from ..exceptions import InvalidChunk


def try_and_close(func):
    def wrapper(self, *args, **kwargs):
        if self._closed:
            return
        try:
            func(self, *args, **kwargs)
        finally:
            self._closed = True
    return wrapper


class ResponseStream(object):
    def __init__(self, session, worker, event_name=""):
        self._closed = False
        self.worker = worker
        self.session = session
        self.event = event_name

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_value is not None:
            self.error(CocaineErrno.EUNCAUGHTEXCEPTION, str(exc_value))
        else:
            self.close()

    def write(self, chunk):
        if not valid_chunk(chunk):
            raise InvalidChunk()

        if not self._closed:
            self.worker.send_chunk(self.session, chunk)
            return

        traceback.print_stack()  # pragma: no cover

    @try_and_close
    def close(self):
        self.worker.send_choke(self.session)

    @try_and_close
    def error(self, code, message):
        self.worker.send_error(self.session, ErrorCategory.CFRAMEWORKCATEGORY, code, message)

    @property
    def closed(self):
        return self._closed
