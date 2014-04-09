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
from __future__ import with_statement

import asyncio
import logging

import msgpack

from cocaine.futures import Deffered
from cocaine.asio.protocol import CocaineProtocol

logging.basicConfig()
log = logging.getLogger("asyncio")
log.setLevel(logging.INFO)


class BaseService(object):
    _state_lock = asyncio.Lock()

    def __init__(self, host='localhost', port=10053, loop=None):
        self.loop = loop or asyncio.get_event_loop()
        self.host = host
        self.port = port
        # protocol
        self.pr = None
        # should I add connection epoch
        # Epoch is usefull when on_failure is called
        self.sessions = dict()
        self.counter = 0

    def connected(self):
        return self.pr and self.pr.connected()

    @asyncio.coroutine
    def connect(self):
        # double state check
        if self.connected():
            log.debug("Connected")
            return

        log.debug("Disconnected")
        with (yield self._state_lock):
            if self.connected():
                return

            log.debug("Still disconnected")
            proto_factory = CocaineProtocol.factory(self.on_message,
                                                    self.on_failure)

            _, self.pr = yield self.loop.create_connection(proto_factory,
                                                           self.host,
                                                           self.port)

    def on_message(self, result):
        msg_type, session, data = result
        log.debug("type %d, session %d, chunk %s", msg_type, session, data)

        deffered = self.sessions.get(session)
        if deffered is None:
            log.error("Unknown session numder %d" % session)
            return

        # replace with constants and message.initializer
        if msg_type == 4:  # RPC CHUNK
            asyncio.async(deffered.push(msgpack.unpackb(data[0])))
        elif msg_type == 6:  # RPC CHOKE
            asyncio.async(deffered.done())
        elif msg_type == 5:  # RPC ERROR
            asyncio.async(deffered.error(*data))

    def on_failure(self, exc):
        log.warn("Disconnected %s", exc)

        for deffered in self.sessions.itervalues():
            log.error("Send DisconnectionError into deffered here!!!")
            # deffered.send_error()

    @asyncio.coroutine
    def _invoke(self, method_id, *args):
        yield self.connect()

        # make it thread-safe
        counter = self.counter
        self.counter += 1

        # send message
        self.pr.write(counter, method_id, *args)

        deffered = Deffered()
        self.sessions[counter] = deffered
        raise asyncio.Return(deffered)


class Locator(BaseService):
    RESOLVE, UPDATE, STATS = xrange(0, 3)

    @asyncio.coroutine
    def resolve(self, name):
        return self._invoke(self.RESOLVE, name)

    @asyncio.coroutine
    def stats(self, name):
        return self._invoke(self.STATS, name)
