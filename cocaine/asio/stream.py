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
import msgpack

from cocaine.concurrent import Deferred

from tornado.iostream import IOStream
from cocaine.services.base import TimeoutDeferred

__author__ = 'Evgeny Safronov <division494@gmail.com>'


class Decoder(object):
    def __init__(self):
        self._unpacker = msgpack.Unpacker()
        self._callback = None

    def set_callback(self, callback):
        self._callback = callback

    def feed(self, data):
        self._unpacker.feed(data)
        if self._callback is None:
            return

        for chunk in self._unpacker:
            self._callback(chunk)


class CocaineStream(object):
    def __init__(self, sock, io_loop):
        self._stream = IOStream(sock, io_loop)
        self._connect_deferred = None
        self._close_callback = None
        self._decoder = Decoder()

    @property
    def connecting(self):
        return self._connect_deferred is not None

    @property
    def connected(self):
        return not self.closed and not self.connecting

    @property
    def closed(self):
        return self._stream.closed()

    @property
    def address(self):
        return self._stream.socket.getsockname()

    def connect(self, address, timeout=None):
        self._connect_deferred = TimeoutDeferred(timeout, self._stream.io_loop)
        self._connect_deferred.add_callback(self._handle_connect_timeout)
        self._stream.connect(address, callback=self._handle_connect)
        self._stream.set_close_callback(self._handle_connect_error)
        return self._connect_deferred

    def write(self, data):
        self._stream.write(data)

    def close(self):
        self._stream.close()

    def set_close_callback(self, callback):
        if self.connecting:
            self._close_callback = callback
        elif self.connected:
            self._stream.set_close_callback(callback)

    def set_read_callback(self, callback):
        self._decoder.set_callback(callback)

    def _handle_connect(self):
        self._stream.read_until_close(lambda data: None, self._decoder.feed)
        self._stream.set_close_callback(self._close_callback)
        deferred = self._connect_deferred
        self._connect_deferred = None
        deferred.trigger()
        deferred.close()

    def _handle_connect_error(self):
        self._stream.set_close_callback(None)
        self._close_callback = None
        deferred = self._connect_deferred
        self._connect_deferred = None
        deferred.error(self._stream.error)
        deferred.close()

    def _handle_connect_timeout(self, future):
        self._stream.set_close_callback(None)
        self._connect_deferred = None
        self._close_callback = None




