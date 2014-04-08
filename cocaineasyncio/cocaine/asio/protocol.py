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


import asyncio

import msgpack


class CocaineProtocol(asyncio.Protocol):
    def __init__(self, on_chunk, on_failure):
        self.buffer = msgpack.Unpacker()
        self.transport = None
        self.on_chunk = on_chunk
        self.on_failure = on_failure

    def connected(self):
        return self.transport is not None

    def connection_made(self, transport):
        self.transport = transport

    def data_received(self, data):
        # Replace with MixIn
        self.buffer.feed(data)
        for chunk in self.buffer:
            self.on_chunk(chunk)

    def connection_lost(self, exc):
        self.transport = None
        self.on_failure(exc)

    def write(self, session, msg_type, *args):
        self.transport.write(msgpack.packb([msg_type, session, args]))

    @staticmethod
    def factory(on_chunk, on_failure):
        return lambda: CocaineProtocol(on_chunk, on_failure)
