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

import json
import time
import sys

from asio import ev
from asio.pipe import Pipe
from asio.stream import ReadableStream
from asio.stream import WritableStream
from asio.stream import Decoder
from asio.message import PROTOCOL_LIST
from asio.message import Message

from cocaine.sessioncontext import Sandbox
from cocaine.sessioncontext import Stream
from cocaine.sessioncontext import Request

from cocaine.logger import Logger
from cocaine.exceptions import RequestError

class Worker(object):

    def __init__(self):
        self._logger = Logger()
        self._init_endpoint()

        self.sessions = dict()
        self.sandbox = Sandbox()

        self.service = ev.Service()

        self.disown_timer = ev.Timer(self.on_disown, 2, self.service)
        self.heartbeat_timer = ev.Timer(self.on_heartbeat, 5, self.service)
        self.disown_timer.start()
        self.heartbeat_timer.start()

        self.pipe = Pipe(self.endpoint)
        self.service.bind_on_fd(self.pipe.fileno())

        self.decoder = Decoder()
        self.decoder.bind(self.on_message)

        self.w_stream = WritableStream(self.service, self.pipe)
        self.r_stream = ReadableStream(self.service, self.pipe)
        self.r_stream.bind(self.decoder.decode)


        self.service.register_read_event(self.r_stream._on_event, self.pipe.fileno())
        self._logger.debug("Worker with %s send handshake" % self.id)
        self._send_handshake()

    def _init_endpoint(self):
        try:
            self.id = sys.argv[sys.argv.index("--uuid") + 1]
            app_name = sys.argv[sys.argv.index("--app") + 1]
            self.endpoint = sys.argv[sys.argv.index("--endpoint") + 1]
        except Exception as err:
            self._logger.error("Wrong cmdline argumensts: %s " % err)
            raise RuntimeError("Wrong cmdline arguments")

    def run(self):
        self.service.run()

    def terminate(self, reason, msg):
        self.w_stream.write(Message("rpc::terminate", 0, reason, msg).pack())
        self.service.stop()

    # Event machine
    def on(self, event, callback):
        self.sandbox.on(event, callback)

    # Events
    def on_heartbeat(self):
        self._send_heartbeat()

    def on_message(self, args):
        msg = Message.initialize(args)
        if msg is None:
            return

        elif msg.id == PROTOCOL_LIST.index("rpc::invoke"):
            try:
                _request = Request()
                _stream = Stream(msg.session, self)
                self.sandbox.invoke(msg.event, _request, _stream)
                self.sessions[msg.session] = _request
            except Exception as err:
                self._logger.error("On invoke error: %s" % err)

        elif msg.id == PROTOCOL_LIST.index("rpc::chunk"):
            _session = self.sessions.get(msg.session, None)
            if _session is not None:
                try:
                    _session.push(msg.data)
                except Exception as err:
                    self._logger.error("On push error: %s" % str(err))

        elif msg.id == PROTOCOL_LIST.index("rpc::choke"):
            _session = self.sessions.get(msg.session, None)
            if _session is not None:
                _session.close()
                self.sessions.pop(msg.session)

        elif msg.id == PROTOCOL_LIST.index("rpc::heartbeat"):
            self.disown_timer.stop()

        elif msg.id == PROTOCOL_LIST.index("rpc::terminate"):
            self.terminate(msg.reason, msg.message)

        elif msg.id == PROTOCOL_LIST.index("rpc::error"):
            _session = self.sessions.get(msg.session, None)
            if _session is not None:
                _session.error(RequestError(msg.message))

    def on_disown(self):
        self.service.stop()

    # Private:
    def _send_handshake(self):
        self.disown_timer.start()
        self.w_stream.write(Message("rpc::handshake", 0, self.id).pack())

    def _send_heartbeat(self):
        self.w_stream.write(Message("rpc::heartbeat", 0).pack())

    def send_choke(self, session):
        self.w_stream.write(Message("rpc::choke", session).pack())

    def send_chunk(self, session, data):
        self.w_stream.write(Message("rpc::chunk", session, data).pack())
