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

import functools

import msgpack

from tornado.iostream import IOStream

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


class CocaineStream(IOStream):
    def __init__(self, socket, *args, **kwargs):
        super(CocaineStream, self).__init__(socket, *args, **kwargs)
        self._decoder = Decoder()

    def connecting(self):
        return self._connecting

    def connected(self):
        return not self.closed() and not self.connecting()

    def address(self):
        if self.socket is not None:
            return self.socket.getsockname()
        else:
            return '0.0.0.0', 0

    def connect(self, address, callback=None, server_hostname=None):
        super(CocaineStream, self).connect(address, functools.partial(self._on_connect, callback), server_hostname)

    def _on_connect(self, callback):
        if callback is not None:
            callback()
        self.read_until_close(lambda data: None, self._decoder.feed)

    def set_read_callback(self, callback):
        self._decoder.set_callback(callback)



