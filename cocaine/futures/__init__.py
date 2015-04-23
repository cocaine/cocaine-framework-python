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

import threading

from tornado.concurrent import Future
from tornado.ioloop import IOLoop


__all__ = ["ConcurrentWorker", "threaded"]


class ConcurrentWorker(object):
    def __init__(self, func, io_loop=None, args=(), kwargs=None):
        self._func = func
        self._io_loop = io_loop or IOLoop.current()
        self._args = args
        self._kwargs = kwargs or {}
        self._future = Future()

        self._worker = threading.Thread(target=self._run)
        self._worker.setDaemon(True)

    def _run(self):
        try:
            result = self._func(*self._args, **self._kwargs)
            self._io_loop.add_callback(self._future.set_result, result)
        except Exception as err:
            self._io_loop.add_callback(self._future.set_exception, err)

    def execute(self):
        self._worker.start()
        return self._future


def threaded(func):
    def wrapper(*args, **kwargs):
        return ConcurrentWorker(func, io_loop=None, args=args, kwargs=kwargs).execute()
    return wrapper
