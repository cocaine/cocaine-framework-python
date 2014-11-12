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

import msgpack
import sys
import threading

from cocaine.asio.exceptions import IllegalStateError
from cocaine.utils import weakmethod


major = sys.version_info[0]
minor = sys.version_info[1]
if major == 2 and minor < 7:
    import array

    class Buffer(array.array):
        def __new__(cls, size):
            return array.array.__new__(cls, 'c', '\0' * size)

        def __len__(self):
            return self.buffer_info()[1]
else:
    class Buffer(bytearray):
        def __init__(self, size):
            super(Buffer, self).__init__('\0' * size)


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
        self._tmp_buff = Buffer(self.START_CHUNK_SIZE)
        self._lock = threading.Lock()

    def bind(self, callback, on_pipe_closed=None):
        assert callable(callback), 'callback argument must be callable'
        with self._lock:
            if self._pipe is None:
                raise IllegalStateError('pipe is not connected')

            self._callback = callback
            self._on_pipe_closed = on_pipe_closed
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
            length = self._pipe.read(self._tmp_buff, len(self._tmp_buff))
            if length <= 0:
                if length == 0:  # Remote side closed the connection
                    # This method stops the polling of fd
                    # in the eventloop.
                    # And it's safe to call it here,
                    # as _pipe.close checks state of the socket.
                    # If pipe is already closed,
                    # this method does nothing.
                    self._pipe.close()

                    # Notify consumer if it wished
                    if self._on_pipe_closed is not None:
                        self._on_pipe_closed()

                    # drop socket ref
                    self._pipe = None
                return

            self._buffer.feed(self._tmp_buff[:length])
            self._callback(self._buffer)

            # Enlarge buffer
            if len(self._tmp_buff) == length:
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
        self._lock = threading.Lock()

    @weakmethod
    def _on_event(self):
        with self._lock:
            self._process_events()

    def _process_events(self):
        # All data has been sent - so unbind writable event
        if len(self._buffer) == 0:
            # Be sure that socket is in a proper connected state
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
            self._process_events()

            if not self._attached and self._pipe.isConnected():
                self._loop.register_write_event(self._on_event, self._pipe.fileno())
                self._attached = True

    def reconnect(self, pipe):
        with self._lock:
            self._pipe = pipe
            self._loop.register_write_event(self._on_event, self._pipe.fileno())
            self._attached = True
            self._tx_offset = 0
