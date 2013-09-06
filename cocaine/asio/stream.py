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
import threading

import msgpack

from cocaine.asio.exceptions import IllegalStateError
from cocaine.utils import weakmethod


class Decoder(object):
    """Decoder middleware.

    .. note:: All methods in this class are reentrant.
    """
    def __init__(self):
        self._callback = None

    def bind(self, callback):
        assert callable(callback), 'callback argument must be callable'
        self._callback = callback

    def decode(self, unpacker):
        for chunk in unpacker:
            self._callback(chunk)


class ReadableStream(object):
    """Represents readable stream for cocaine protocol.

    .. note:: All methods in this class are thread safe.
    """
    START_CHUNK_SIZE = 4096

    def __init__(self, loop, pipe):
        self._loop = loop
        self._pipe = pipe

        self._callback = None
        self._attached = False
        self._buffer = msgpack.Unpacker()
        self._tmp_buff = array.array('c', '\0' * self.START_CHUNK_SIZE)
        self._lock = threading.Lock()

    def bind(self, callback):
        assert callable(callback), 'callback argument must be callable'
        with self._lock:
            if self._pipe is None:
                raise IllegalStateError('pipe is not connected')

            self._callback = callback
            self._attached = self._loop.register_read_event(self._on_event, self._pipe.fileno())

    def unbind(self):
        with self._lock:
            if not self._pipe:
                raise IllegalStateError('pipe is not connected')

            self._callback = None
            if self._attached:
                self._loop.unregister_read_event(self._pipe.fileno())

    def reconnect(self, pipe):
        with self._lock:
            self._pipe = pipe
            self._buffer = msgpack.Unpacker()
            self.bind(self._callback)

    @weakmethod
    def _on_event(self):
        with self._lock:
            if self._pipe is None:
                raise IllegalStateError('pipe is not connected')

            # Bad solution. On python 2.7 and higher - use memoryview and bytearray
            length = self._pipe.read(self._tmp_buff, self._tmp_buff.buffer_info()[1])
            if length <= 0:
                if length == 0:
                    # Remote side has closed connection
                    self._loop.stop_listening(self._pipe.fileno())
                    self._pipe = None
                return

            self._buffer.feed(self._tmp_buff[:length])
            self._callback(self._buffer)

            # Enlarge buffer if it is not large enough
            if self._tmp_buff.buffer_info()[1] == length:
                self._tmp_buff *= 2


class WritableStream(object):
    """Represents writable stream for cocaine protocol.

    .. note:: All methods in this class are thread safe.
    """
    def __init__(self, loop, pipe):
        self._loop = loop
        self._pipe = pipe

        self._attached = False
        self._buffer = list()
        self._tx_offset = 0
        self._lock = threading.RLock()

    @weakmethod
    def _on_event(self):
        with self._lock:
            # All data was sent - so unbind writable event
            if len(self._buffer) == 0:
                if self._attached:
                    self._loop.unregister_write_event(self._pipe.fileno())
                    self._attached = False
                return

            can_write = True
            while can_write and len(self._buffer) > 0:
                current = self._buffer[0]
                sent = self._pipe.write(buffer(current, self._tx_offset))

                if sent > 0:
                    self._tx_offset += sent
                else:
                    can_write = False

                # Current object is sent completely - pop it from buffer
                if self._tx_offset == len(current):
                    self._buffer.pop(0)
                    self._tx_offset = 0

    def write(self, data):
        with self._lock:
            self._buffer.append(msgpack.dumps(data))
            self._on_event()

            if not self._attached and self._pipe.isConnected():
                self._loop.register_write_event(self._on_event, self._pipe.fileno())
                self._attached = True

    def reconnect(self, pipe):
        with self._lock:
            self._pipe = pipe
            self._loop.register_write_event(self._on_event, self._pipe.fileno())
            self._attached = True
            self._tx_offset = 0
