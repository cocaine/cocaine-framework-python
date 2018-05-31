#
#    Copyright (c) 2014+ Anton Tyurin <noxiouz@yandex.ru>
#    Copyright (c) 2014+ Evgeny Safronov <division494@gmail.com>
#    Copyright (c) 2011-2014 Other contributors as noted in the AUTHORS file.
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

import os
import sys

import msgpack

from tornado import netutil
from tornado import ioloop
from tornado import gen
from tornado import tcpserver


METHOD = 'POST'
URI = '/blabla?arg=1'
HTTP_VERSION = '1.1'
HEADERS = [['User-Agent', 'curl/7.22.0 (x86_64-pc-linux-gnu) libcurl/7.22.0 OpenSSL/1.0.1 zlib/1.2.3.4 libidn/1.23 librtmp/2.3'],
           ['Host', 'localhost:8080'], ['Accept', '*/*'], ['Content-Length', '6'], ['Content-Type', 'application/x-www-form-urlencoded'],
           ['Cookie', 'C=D']]
BODY = b'dsdsds'


class RuntimeMock(tcpserver.TCPServer):
    _msgpack_string_encoding = None if sys.version_info[0] == 2 else 'utf8'

    def __init__(self, unixsocket):
        super(RuntimeMock, self).__init__()
        self.actions = list()
        self.counter = 1
        self.endpoint = unixsocket
        self.add_socket(netutil.bind_unix_socket(unixsocket))

    def on(self, message, action):
        self.actions.append((message, action))

    @gen.coroutine
    def handle_stream(self, stream, address):
        buff = msgpack.Unpacker()
        while True:
            data = yield stream.read_bytes(1024, partial=True)
            buff.feed(data)
            for i in buff:
                try:
                    handlers = [cbk for trigger, cbk in self.actions if trigger == i]
                    for h in handlers:
                        yield h(stream)
                except Exception as err:
                    print(err)

    def stop(self):
        self.io_loop.stop()
        os.remove(self.endpoint)


def main_v0(path, timeout=10):
    loop = ioloop.IOLoop()
    loop.make_current()
    s = RuntimeMock(path)

    @gen.coroutine
    def on_heartbeat_v0(w):
        if sys.version_info[0] == 2:
            packer = msgpack.Packer()
        else:
            packer = msgpack.Packer(use_bin_type=True)
        if s.counter > 6:
            yield w.write(packer.pack([1, 2, [2, "terminate"]]))
            s.io_loop.add_callback(s.stop)
            return
        req = [METHOD, URI, HTTP_VERSION, HEADERS, BODY]
        yield w.write(packer.pack([1, 1, []]))
        yield w.write(packer.pack([s.counter, 3, ["ping"]]))
        yield w.write(packer.pack([s.counter, 4, ["pong"]]))
        yield w.write(packer.pack([s.counter, 6, []]))
        s.counter += 1
        yield w.write(packer.pack([s.counter, 3, ["bad_event"]]))
        s.counter += 1
        yield w.write(packer.pack([s.counter, 3, ["http"]]))
        yield w.write(packer.pack([s.counter, 4, [packer.pack(req)]]))
        yield w.write(packer.pack([s.counter, 6, []]))
        s.counter += 1
        yield w.write(packer.pack([s.counter, 3, ["http_test"]]))
        yield w.write(packer.pack([s.counter, 4, [packer.pack(req)]]))
        yield w.write(packer.pack([s.counter, 6, []]))
        s.counter += 1
        yield w.write(packer.pack([s.counter + 100, 4, ["bad_ping"]]))
        yield w.write(packer.pack([s.counter, 104, ["bad_ping"]]))
        s.counter += 1
        yield w.write(packer.pack([s.counter, 3, ["bad_ping"]]))
        yield w.write(packer.pack([s.counter, 4, ["A"]]))
        yield w.write(packer.pack([s.counter, 6, []]))
        s.counter += 1
        yield w.write(packer.pack([s.counter, 3, ["notclosed"]]))
        yield w.write(packer.pack([s.counter, 4, ["A"]]))
        yield w.write(packer.pack([s.counter, 6, []]))
    s.on([1, 1, []], on_heartbeat_v0)
    s.io_loop.call_later(timeout, s.io_loop.stop)


def main_v1(path, timeout=10):
    loop = ioloop.IOLoop()
    loop.make_current()
    s = RuntimeMock(path)

    @gen.coroutine
    def on_heartbeat_v1(w):
        if sys.version_info[0] == 2:
            packer = msgpack.Packer()
        else:
            packer = msgpack.Packer(use_bin_type=True)
        if s.counter > 6:
            yield w.write(packer.pack([1, 1, [2, "terminate"]]))
            s.io_loop.add_callback(s.stop)
            return
        req = [METHOD, URI, HTTP_VERSION, HEADERS, BODY]
        yield w.write(packer.pack([1, 0, []]))
        s.counter += 1
        yield w.write(packer.pack([s.counter, 0, ["ping"], (80, [True, "PING", "A"])]))
        yield w.write(packer.pack([s.counter, 0, ["pong"], ([False, 83, "B"],)]))
        yield w.write(packer.pack([s.counter, 2, []]))
        s.counter += 1
        yield w.write(packer.pack([s.counter, 0, ["bad_event"]]))
        s.counter += 1
        yield w.write(packer.pack([s.counter, 0, ["http"]]))
        yield w.write(packer.pack([s.counter, 0, [packer.pack(req)]]))
        yield w.write(packer.pack([s.counter, 2, []]))
        s.counter += 1
        yield w.write(packer.pack([s.counter, 0, ["http_test"]]))
        yield w.write(packer.pack([s.counter, 0, [packer.pack(req)]]))
        yield w.write(packer.pack([s.counter, 2, []]))
        s.counter += 1
        yield w.write(packer.pack([s.counter + 100, 2, ["bad_ping"]]))
        yield w.write(packer.pack([s.counter, 104, ["bad_ping"]]))
        s.counter += 1
        yield w.write(packer.pack([s.counter, 0, ["bad_ping"]]))
        yield w.write(packer.pack([s.counter, 0, ["A"]]))
        yield w.write(packer.pack([s.counter, 2, []]))
        s.counter += 1
        yield w.write(packer.pack([s.counter, 0, ["notclosed"]]))
        yield w.write(packer.pack([s.counter, 0, ["A"]]))
        yield w.write(packer.pack([s.counter, 2, []]))
        s.counter += 1
        yield w.write(packer.pack([s.counter, 0, ["err_res"]]))
        yield w.write(packer.pack([s.counter, 1, [(-100, 100), "test_err"]]))
    s.on([1, 0, []], on_heartbeat_v1)
    s.io_loop.call_later(timeout, s.io_loop.stop)


if __name__ == '__main__':
    main_v0("enp")
