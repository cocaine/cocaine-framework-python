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

import msgpack
import array

from threading import Lock

MAX_BUFF_SIZE = 104857600
START_CHUNK_SIZE = 1024

def encode_dec(f):
    def wrapper(self, data):
        encode = msgpack.packb(data)
        return f(self, encode, len(encode))
    return wrapper

class Decoder(object):

    def __init__(self):
        self.m_callback = None

    def bind(self, callback):
        assert callable(callback)
        self.m_callback = callback

    def decode(self, data):
        unpacker = msgpack.Unpacker()
        unpacker.feed(data)
        parsed_len = 0
        try:
            for res in unpacker:
                parsed_len += len(msgpack.packb(res))
                self.m_callback(res)
        except Exception as err:
            pass # hook - view later
        finally:
            return parsed_len


class ReadableStream(object):

    def __init__(self, service, pipe):
        self.m_service = service
        self.m_pipe = pipe

        self.m_callback = None
        self.is_attached = False

        self.m_ring = array.array('c')
        self.tmp_buff = array.array('c','\0' * START_CHUNK_SIZE)
        self.m_rd_offset = 0
        self.m_rx_offset = 0

    def bind(self, callback):
        assert callable(callback)
        self.m_callback = callback
        self.is_attached = self.m_service.register_read_event(self._on_event, self.m_pipe.fileno())

    def unbind(self):
        self.m_callback = None
        if self.is_attached:
            self.m_service.unregister_read_evnt(self.m_pipe.fileno())

    def _on_event(self):
        unparsed = self.m_rd_offset - self.m_rx_offset
        if len(self.m_ring) > MAX_BUFF_SIZE:
            self.m_ring = array.array('c', self.m_ring[self.m_rx_offset : self.m_rx_offset + unparsed])
            self.m_rd_offset = unparsed
            self.m_rx_offset = 0

        # Bad solution. On python 2.7 and higher - use memoryview and bytearray
        length = self.m_pipe.read(self.tmp_buff, self.tmp_buff.buffer_info()[1])
        if length <= 0:
            if length == 0: #Remote side has closed connection
                self.m_service.unregister_read_event(self.m_pipe.fileno())
            return

        self.m_rd_offset += length
        self.m_ring.extend(self.tmp_buff[:length])

        parsed = self.m_callback(self.m_ring[self.m_rx_offset : self.m_rd_offset])
        self.m_rx_offset += parsed

        # Enlarge buffer if messages are big
        if self.tmp_buff.buffer_info()[1] == length:
            self.tmp_buff *= 2


class WritableStream(object):

    def __init__(self, service, pipe):
        self.m_service = service
        self.m_pipe = pipe
        self.is_attached = False#service.register_write_event(self._on_event, pipe.fileno())

        self.m_mutex = Lock()

        self.m_ring = array.array('c')
        self.tmp_buff = array.array('c','\0' * START_CHUNK_SIZE)
        self.m_wr_offset = 0
        self.m_tx_offset = 0

    def _on_event(self):
        print "WRIETE ON EVENT"
        with self.m_mutex:

            if len(self.m_ring) == 0 and self.is_attached:
                self.m_service.unregister_write_event(self.m_pipe.fileno())
                self.is_attached = False
                return

            unsent = self.m_wr_offset - self.m_tx_offset

            sent = self.m_pipe.write(self.m_ring[self.m_tx_offset : self.m_tx_offset+unsent])

            if sent > 0:
                self.m_tx_offset += sent

    @encode_dec
    def write(self, data, size):
        with self.m_mutex:
            if self.m_wr_offset == self.m_tx_offset:
                sent = self.m_pipe.write(data)

                if sent >= 0:
                    if sent == size:
                        return

                    size -= sent

            if len(self.m_ring) > MAX_BUFF_SIZE:
                self.m_ring = array.array('c', self.m_ring[self.m_tx_offset : self.m_tx_offset + unsent])
                self.m_rd_offset = unsent
                self.m_rx_offset = 0


            self.m_wr_offset += size
            self.m_ring.extend(data[sent:])


            if False == self.is_attached:
                self.m_service.register_write_event(self._on_event, self.m_pipe.fileno())
                self.is_attached = True
