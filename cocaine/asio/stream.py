# encoding: utf-8
#
#    Copyright (c) 2011-2013 Anton Tyurin <noxiouz@yandex.ru>
#    Copyright (c) 2011-2013 Other contributors as noted in the AUTHORS file.
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

import array
import collections
from threading import Lock

import msgpack

from cocaine.utils import weakmethod

START_CHUNK_SIZE = 10240


def encode_dec(f):
    def wrapper(self, data):
        encode = msgpack.packb(data)
        return f(self, encode, len(encode))
    return wrapper


class Decoder(object):
    def __init__(self):
        self.callback = None

    def bind(self, callback):
        assert callable(callback)
        self.callback = callback

    def decode(self, buffer):
        """
         buffer is msgpack.Unpacker (stream unpacker)
        """
        # if not enough data - 0 iterations
        for res in buffer:
            self.callback(res)


class ReadableStream(object):
    def __init__(self, loop, pipe):
        self.loop = loop
        self.pipe = pipe

        self.callback = None
        self.is_attached = False

        self.buffer = msgpack.Unpacker()
        self.tmp_buff = array.array('c', '\0' * START_CHUNK_SIZE)
        self.mutex = Lock()

    def bind(self, callback):
        assert callable(callback)
        self.callback = callback
        self.is_attached = self.loop.register_read_event(self._on_event, self.pipe.fileno())

    def unbind(self):
        self.callback = None
        if self.is_attached:
            self.loop.unregister_read_event(self.pipe.fileno())

    @weakmethod
    def _on_event(self):
        with self.mutex:
            # Bad solution. On python 2.7 and higher - use memoryview and bytearray
            length = self.pipe.read(self.tmp_buff, self.tmp_buff.buffer_info()[1])

            if length <= 0:
                if length == 0:  # Remote side has closed connection
                    self.pipe.connected = False
                    self.loop.stop_listening(self.pipe.fileno())
                return

            self.buffer.feed(self.tmp_buff[:length])
            self.callback(self.buffer)

            # Enlarge buffer if messages are big
            if self.tmp_buff.buffer_info()[1] == length:
                self.tmp_buff *= 2

    def reconnect(self, pipe):
        self.pipe = pipe
        self.buffer = msgpack.Unpacker()
        self.bind(self.callback)


class WritableStream(object):
    def __init__(self, loop, pipe):
        self.loop = loop
        self.pipe = pipe
        self.is_attached = False

        self._buffer = list()
        self.tx_offset = 0

    @weakmethod
    def _on_event(self):
        # All data was sent - so unbind writable event
        if not self._buffer:
            if self.is_attached:
                self.loop.unregister_write_event(self.pipe.fileno())
                self.is_attached = False
            return

        can_write = True
        while can_write and self._buffer:
            print(len(self._buffer))
            current = self._buffer[0]
            sent = self.pipe.write(buffer(current, self.tx_offset))

            if sent > 0:
                self.tx_offset += sent
            else:
                can_write = False

            # Current object is sent completely - pop it from buffer
            if self.tx_offset == len(current):
                self._buffer.pop(0)
                self.tx_offset = 0

    @encode_dec
    def write(self, data, size):
        self._buffer.append(data)
        self._on_event()

        if not self.is_attached and self.pipe.connected:
            self.loop.register_write_event(self._on_event, self.pipe.fileno())
            self.is_attached = True

    def reconnect(self, pipe):
        self.pipe = pipe
        self.loop.register_write_event(self._on_event, self.pipe.fileno())
        self.is_attached = True
        self.tx_offset = 0
