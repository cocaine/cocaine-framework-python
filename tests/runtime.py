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

import os
import trollius as asyncio
import logging

logging.basicConfig()
log = logging.getLogger("asyncio")
log.setLevel(logging.DEBUG)


class RuntimeMock(object):
    def __init__(self, unixsocket, loop=None):
        self.loop = loop or asyncio.get_event_loop()
        self.endpoint = unixsocket
        self.actions = list()
        self.event = asyncio.Event()
        self.counter = 1

    def serve(self):
        @asyncio.coroutine
        def _serve():
            yield asyncio.async(asyncio.start_unix_server(self.on_client,
                                                          path=self.endpoint,
                                                          loop=self.loop))
            yield self.event.wait()

        try:
            self.loop.run_until_complete(_serve())
        finally:
            os.remove(self.endpoint)

    def on(self, message, action):
        self.actions.append((message, action))

    @asyncio.coroutine
    def on_client(self, reader, writer):
        buff = msgpack.Unpacker()
        while not reader.at_eof():
            data = yield reader.read(100)
            buff.feed(data)
            for i in buff:
                log.info("%s", i)
                try:
                    map(lambda clb: apply(clb, (writer,)),
                        [cbk for trigger, cbk in self.actions if trigger == i])
                except Exception as err:
                    log.exception(err)

    def stop(self):
        self.event.set()


def install_server(path):
    l = asyncio.get_event_loop()
    r = RuntimeMock(path, loop=l)
    return r


def main(path):
    r = install_server(path)

    def on_heartbeat(w):
        w.write(msgpack.packb([1, 1, []]))
        w.write(msgpack.packb([r.counter, 3, ["ping"]]))
        w.write(msgpack.packb([r.counter, 4, ["ping"]]))
        w.write(msgpack.packb([r.counter, 6, []]))
        r.counter += 1
        w.write(msgpack.packb([r.counter, 3, ["bad_event"]]))
        if r.counter > 2:
            r.stop()

    r.on([1, 1, []], on_heartbeat)
    r.serve()


def terminate(path):
    pass

if __name__ == '__main__':
    main("enp")
