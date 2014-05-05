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

import logging
import sys

import asyncio

from cocaine.asio.message import RPC
from cocaine.asio.message import Message
from cocaine.asio.utils import Timer
from cocaine.asio import CocaineProtocol

from .sandbox import Sandbox

DEFAULT_HEARTBEAT_TIMEOUT = 20
DEFAULT_DISOWN_TIMEOUT = 5

logging.basicConfig()
log = logging.getLogger("asyncio")
log.setLevel(logging.DEBUG)


class Worker(object):
    def __init__(self, disown_timeout=DEFAULT_DISOWN_TIMEOUT,
                 heartbeat_timeout=DEFAULT_HEARTBEAT_TIMEOUT,
                 loop=None, **kwargs):
        self.loop = loop or asyncio.get_event_loop()

        self.disown_timer = Timer(self.on_disown,
                                  disown_timeout, self.loop)

        self.heartbeat_timer = Timer(self.on_heartbeat,
                                     heartbeat_timeout, self.loop)

        self._sandbox = Sandbox()
        self._dispatcher = {
            # RPC.HEARTBEAT: self._dispatch_heartbeat,
            # RPC.TERMINATE: self._dispatch_terminate,
            # RPC.INVOKE: self._dispatch_invoke,
            # RPC.CHUNK: self._dispatch_chunk,
            # RPC.ERROR: self._dispatch_error,
            # RPC.CHOKE: self._dispatch_choke
        }

        #TBD move into opts
        try:
            self.appname = kwargs.get("app") or sys.argv[sys.argv.index("--app") + 1]
            self.uuid = kwargs.get("uuid") or sys.argv[sys.argv.index("--uuid") + 1]
            self.endpoint = kwargs.get("endpoint") or sys.argv[sys.argv.index("--endpoint") + 1]
        except (ValueError, IndexError) as err:
            raise Exception("Wrong commandline args %s" % err)

        self._sessiong = {}
        # protocol
        self.pr = None

        proto_factory = CocaineProtocol.factory(self.on_message,
                                                self.on_failure)

        @asyncio.coroutine
        def on_connect():
            log.debug("Connected to %s", self.endpoint)
            try:
                self.pr = yield self.loop.create_unix_connection(proto_factory,
                                                                 self.endpoint)
                log.debug("Connected to %s", self.endpoint)
                return
            except asyncio.FileNotFoundError as err:
                log.error("Unable to connect to UNIX socket '%s'. No such file.", self.endpoint)
            except Exception as err:
                log.error("Unable to connect to '%s' %s", self.endpoint, err)
            self.on_failure()

        asyncio.async(on_connect(), self.loop)

    def run(self, binds=None):
        if binds is None:
            binds = {}
        # attach handlers
        for event, handler in binds.iteritems():
            self.on(event, handler)

        if not self.loop.is_running():
            self.loop.run_forever()

    def on(self, event, callback):
        self._sandbox.on(event, callback)

    # Events
    # healtmonitoring events
    def on_heartbeat(self):
        self._send_heartbeat()

    def on_disown(self):
        try:
            log.error("Disowned")
        finally:
            self.loop.stop()

    # General dispathc method
    def on_message(self, args):
        log.debug("on_message")
        message = Message.initialize(args)
        callback = self._dispatcher.get(message.id)
        if callback is None:
            raise Exception("Unknown message type %s" % str(message))

        callback(message)

    # On disconnection callback
    def on_failure(self, *args):
        log.error("on_failure")
        self.on_disown()
