#
#    Copyright (c) 2013+ Evgeny Safronov <division494@gmail.com>
#    Copyright (c) 2011-2013 Other contributors as noted in the AUTHORS file.
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
import contextlib
import time

from cocaine import concurrent

__author__ = 'Evgeny Safronov <division494@gmail.com>'


class strategy:
    @classmethod
    def init(cls, func, isBlocking):
        return strategy.sync(func) if isBlocking else strategy.async(func)

    @classmethod
    def coroutine(cls, func):
        def wrapper(*args, **kwargs):
            blocking = kwargs.get('blocking', False)
            return strategy.init(func, blocking)(*args, **kwargs)
        return wrapper

    @classmethod
    def sync(cls, func):
        def wrapper(*args, **kwargs):
            g = func(*args, **kwargs)
            chunk = None
            while True:
                try:
                    chunk = g.send(chunk)
                except StopIteration:
                    break
        return wrapper

    @classmethod
    def async(cls, func):
        return concurrent.engine(func)


@contextlib.contextmanager
def cumulative(timeout):
    start = time.time()

    def timeLeft():
        return timeout - (time.time() - start) if timeout is not None else None
    yield timeLeft


class scope(object):
    class socket(object):
        @classmethod
        @contextlib.contextmanager
        def blocking(cls, sock):
            try:
                sock.setblocking(True)
                yield sock
            finally:
                sock.setblocking(False)

        @classmethod
        @contextlib.contextmanager
        def timeout(cls, sock, timeout):
            try:
                sock.settimeout(timeout)
                yield sock
            finally:
                sock.settimeout(0.0)