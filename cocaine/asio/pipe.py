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

import socket
import time

from tornado import iostream

from cocaine.concurrent import Deferred

__author__ = 'Evgeny Safronov <division494@gmail.com>'


class StreamError(IOError):
    pass


def make_timed(timeout_id, io_loop):
    def timed(func):
        def wrapper(*args, **kwargs):
            func(*args, **kwargs)
            io_loop.remove_timeout(timeout_id)
        return wrapper
    return timed


class Stream(object):
    def __init__(self, sock, io_loop):
        self._stream = iostream.IOStream(sock, io_loop)
        self._stream.set_nodelay(True)

        self.read_until_close = self._stream.read_until_close
        self.write = self._stream.write
        self.set_close_callback = self._stream.set_close_callback
        self.close = self._stream.close
        self.reading = self._stream.reading
        self.writing = self._stream.writing

        self._connect_deferred = None

    def connect(self, address, timeout=None):
        if self.connecting:
            return self._connect_deferred

        self._connect_deferred = Deferred()

        if timeout:
            def on_timeout():
                self._stream.io_loop.remove_timeout(timeout_id)
                self._stream.set_close_callback(None)
                self._stream.close()
                self._connect_deferred.error(socket.error('timeout'))
            timeout_id = self._stream.io_loop.add_timeout(time.time() + timeout, on_timeout)
            timed = make_timed(timeout_id, self._stream.io_loop)
        else:
            timed = lambda func: func

        @timed
        def on_connect():
            self._stream.set_close_callback(None)
            self._connect_deferred.trigger()
            self._connect_deferred = None

        @timed
        def on_close():
            self._stream.set_close_callback(None)
            self._connect_deferred.error(self._stream.error)
            self._connect_deferred = None

        self._stream.connect(address, on_connect)
        self._stream.set_close_callback(on_close)
        return self._connect_deferred

    @property
    def closed(self):
        return self._stream.closed()

    @property
    def connecting(self):
        return not self.closed and self._stream._connecting

    @property
    def connected(self):
        return not self.closed and not self._stream._connecting
