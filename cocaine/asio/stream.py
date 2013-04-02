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
from threading import Lock

import msgpack

MAX_BUFF_SIZE = 104857600
START_CHUNK_SIZE = 1024

def encode_dec(f):
    def wrapper(self, data):
        #print "SEND", data
        encode = msgpack.packb(data)
        return f(self, encode, len(encode))
    return wrapper

class Decoder(object):

    def __init__(self):
        self.callback = None

    def bind(self, callback):
        assert callable(callback)
        self.callback = callback

    def decode(self, data):
        unpacker = msgpack.Unpacker()
        unpacker.feed(data)
        parsed_len = 0
        try:
            for res in unpacker:
                parsed_len += len(msgpack.packb(res))
                #print "Decode:",  res
                self.callback(res)
        except Exception as err:
            pass # hook - view later
        finally:
            return parsed_len


class ReadableStream(object):

    def __init__(self, service, pipe):
        self.service = service
        self.pipe = pipe

        self.callback = None
        self.is_attached = False

        self.ring = array.array('c')
        self.tmp_buff = array.array('c','\0' * START_CHUNK_SIZE)
        self.rd_offset = 0
        self.rx_offset = 0

    def bind(self, callback):
        assert callable(callback)
        self.callback = callback
        self.is_attached = self.service.register_read_event(self._on_event, self.pipe.fileno())

    def unbind(self):
        self.callback = None
        if self.is_attached:
            self.service.unregister_read_evnt(self.pipe.fileno())

    def _on_event(self):
        unparsed = self.rd_offset - self.rx_offset
        if len(self.ring) > MAX_BUFF_SIZE:
            self.ring = array.array('c', self.ring[self.rx_offset : self.rx_offset + unparsed])
            self.rd_offset = unparsed
            self.rx_offset = 0

        # Bad solution. On python 2.7 and higher - use memoryview and bytearray
        length = self.pipe.read(self.tmp_buff, self.tmp_buff.buffer_info()[1])
        if length <= 0:
            if length == 0: #Remote side has closed connection
                self.service.unregister_read_event(self.pipe.fileno())
            return

        self.rd_offset += length
        self.ring.extend(self.tmp_buff[:length])

        parsed = self.callback(self.ring[self.rx_offset : self.rd_offset])
        self.rx_offset += parsed

        # Enlarge buffer if messages are big
        if self.tmp_buff.buffer_info()[1] == length:
            self.tmp_buff *= 2


class WritableStream(object):

    def __init__(self, service, pipe):
        self.service = service
        self.pipe = pipe
        self.is_attached = False#service.register_write_event(self._on_event, pipe.fileno())

        self.mutex = Lock()

        self.ring = array.array('c')
        self.tmp_buff = array.array('c','\0' * START_CHUNK_SIZE)
        self.wr_offset = 0
        self.tx_offset = 0

    def _on_event(self):
        with self.mutex:

            if len(self.ring) == 0 and self.is_attached:
                self.service.unregister_write_event(self.pipe.fileno())
                self.is_attached = False
                return

            unsent = self.wr_offset - self.tx_offset

            sent = self.pipe.write(self.ring[self.tx_offset : self.tx_offset+unsent])

            if sent > 0:
                self.tx_offset += sent

    @encode_dec
    def write(self, data, size):
        with self.mutex:
            if self.wr_offset == self.tx_offset:
                sent = self.pipe.write(data)

                if sent >= 0:
                    if sent == size:
                        return

                    size -= sent

            if len(self.ring) > MAX_BUFF_SIZE:
                self.ring = array.array('c', self.ring[self.tx_offset : self.tx_offset + unsent])
                self.rd_offset = unsent
                self.rx_offset = 0


            self.wr_offset += size
            self.ring.extend(data[sent:])


            if False == self.is_attached:
                self.service.register_write_event(self._on_event, self.pipe.fileno())
                self.is_attached = True
