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

        self._buffer = collections.deque()

    @weakmethod
    def _on_event(self):
        # All data was sent - so unbind writable event
        if not self._buffer:
            self.loop.unregister_write_event(self.pipe.fileno())
            self.is_attached = False
            return

        # Empty the buffer
        while self._buffer:
            num_bytes = self.pipe.write(self._buffer[0])
            if num_bytes == 0:
                break
            merge_prefix(self._buffer, num_bytes)
            self._buffer.popleft()


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


def merge_prefix(deque, size):
    if len(deque) == 1 and len(deque[0]) <= size:
        return
    prefix = []
    remaining = size
    while deque and remaining > 0:
        chunk = deque.popleft()
        if len(chunk) > remaining:
            deque.appendleft(chunk[remaining:])
            chunk = chunk[:remaining]
        prefix.append(chunk)
        remaining -= len(chunk)

    if prefix:
        deque.appendleft(type(prefix[0])().join(prefix))
    if not deque:
        deque.appendleft(b'')
