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

import msgpack

from tornado import netutil
from tornado import ioloop
from tornado import gen
from tornado import tcpserver


class RuntimeMock(tcpserver.TCPServer):
    def __init__(self, unixsocket, io_loop=None):
        super(RuntimeMock, self).__init__(io_loop=io_loop or ioloop.IOLoop.current())
        self.io_loop = io_loop or ioloop.IOLoop.current()
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
                    map(lambda clb: apply(clb, (stream,)),
                        [cbk for trigger, cbk in self.actions if trigger == i])
                except Exception as err:
                    print(err)

    def stop(self):
        self.io_loop.stop()


def main(path, timeout=10):
    loop = ioloop.IOLoop()
    loop.make_current()
    s = RuntimeMock(path)

    def on_heartbeat(w):
        w.write(msgpack.packb([1, 1, []]))
        w.write(msgpack.packb([s.counter, 3, ["ping"]]))
        w.write(msgpack.packb([s.counter, 4, ["ping"]]))
        w.write(msgpack.packb([s.counter, 6, []]))
        s.counter += 1
        w.write(msgpack.packb([s.counter, 3, ["bad_event"]]))
        if s.counter > 2:
            s.stop()

    s.on([1, 1, []], on_heartbeat)
    s.io_loop.call_later(timeout, s.io_loop.stop)
    s.io_loop.start()

if __name__ == '__main__':
    main("enp")
