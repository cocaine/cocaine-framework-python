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


import uuid
import json
import time
import sys
import struct

from asio_worker import ev
from asio_worker.pipe import Pipe
from asio_worker.stream import ReadableStream
from asio_worker.stream import WritableStream
from asio_worker.stream import Decoder

from asio_worker.message import PROTOCOL_LIST
from asio_worker.message import Message

from sessioncontext import Sandbox
from sessioncontext import Stream

class Unique_id(object):

    def __init__(self, _uuid):
        u = uuid.UUID(_uuid)
        self.id = struct.unpack('LL', u.bytes )

class Worker(object):

    def __init__(self):
        self._init_endpoint()

        self.sessions = dict()
        self.m_sandbox = Sandbox()

        self.m_service = ev.Service()

        self.m_disown_timer = ev.Timer(self.on_disown, 2, self.m_service)
        self.m_heartbeat_timer = ev.Timer(self.on_heartbeat, 5, self.m_service)
        self.m_disown_timer.start()
        self.m_heartbeat_timer.start()

        self.m_pipe = Pipe(self.endpoint)
        self.m_service.bind_on_fd(self.m_pipe.fileno())

        self.m_decoder = Decoder()
        self.m_decoder.bind(self.on_message)

        self.m_w_stream = WritableStream(self.m_service, self.m_pipe)
        self.m_r_stream = ReadableStream(self.m_service, self.m_pipe)
        self.m_r_stream.bind(self.m_decoder.decode)


        self.m_service.register_read_event(self.m_r_stream._on_event, self.m_pipe.fileno())
        self._send_handshake()

    def _init_endpoint(self):
        try:
            uuid=sys.argv[sys.argv.index("--uuid") + 1]
            app_name = sys.argv[sys.argv.index("--app") + 1]
            self.endpoint = sys.argv[sys.argv.index("--endpoint") + 1]
            self.m_id = Unique_id(uuid).id
        except Exception as err:
            raise RuntimeError("Wrong cmdline arguments")

    def run(self):
        self.m_service.run()

    def terminate(self, reason, msg):
        self.m_w_stream.write(Message("rpc::terminate", 0, reason, msg).pack())
        self.m_service.stop()

    # Event machine
    def on(self, event, callback):
        self.m_sandbox.on(event, callback)

    # Events
    def on_heartbeat(self):
        self._send_heartbeat()

    def on_message(self, args):
        msg = Message.initialize(args)
        if msg is None:
            #print "Worker %s dropping unknown message %s" % (self.m_id, str(args))
            return

        elif msg.id == PROTOCOL_LIST.index("rpc::invoke"):
            #print "Receive invoke: %s %s" % (msg.event, msg.session)
            _stream = Stream(msg.session, self)
            self.sessions[msg.session] = (_stream, self.m_sandbox.invoke(msg.event, _stream))

        elif msg.id == PROTOCOL_LIST.index("rpc::chunk"):
            #print "Receive chunk: %s" % msg.session
            _session = self.sessions.get(msg.session, None)
            if _session is not None:
                _session[1].push(msg.data)

        elif msg.id == PROTOCOL_LIST.index("rpc::choke"):
            #print "Receive choke: %s" % msg.session
            _session = self.sessions.get(msg.session, None)
            if _session is not None:
                _session[1].close()
                self.sessions.pop(msg.session)

        elif msg.id == PROTOCOL_LIST.index("rpc::heartbeat"):
            #print "Receive heartbeat. Restart disown timer"
            self.m_disown_timer.stop()

        elif msg.id == PROTOCOL_LIST.index("rpc::terminate"):
            #print "Receive terminate"
            self.terminate(msg.reason, msg.message)

    def on_disown(self):
        #print "Worker has lost controlling engine"
        self.m_service.stop()

    # Private:
    def _send_handshake(self):
        #print "Send handshake"
        self.m_w_stream.write(Message("rpc::handshake", 0, self.m_id).pack())
        self.m_disown_timer.start()

    def _send_heartbeat(self):
        #print "Send heartbeat"
        self.m_w_stream.write(Message("rpc::heartbeat", 0).pack())

    def send_choke(self, session):
        #print "send choke"
        self.m_w_stream.write(Message("rpc::choke", session).pack())

    def send_chunk(self, session, data):
        #print "send chunk"
        self.m_w_stream.write(Message("rpc::chunk", session, data).pack())
