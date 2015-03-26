# encoding: utf-8
#
#    Copyright (c) 2011-2013 Anton Tyurin <noxiouz@yandex.ru>
#    Copyright (c) 2011-2013 Other contributors as noted in the AUTHORS file.
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
import socket

import sys
import traceback
import types

from cocaine.asio import ev
from cocaine.asio.pipe import Pipe
from cocaine.asio.stream import ReadableStream
from cocaine.asio.stream import WritableStream
from cocaine.asio.stream import Decoder
from cocaine.asio import message
from cocaine.asio.message import Message

from cocaine.sessioncontext import Sandbox
from cocaine.sessioncontext import Stream
from cocaine.sessioncontext import Request

from cocaine.logging.log import core_log
from cocaine.exceptions import RequestError
from cocaine.disowntimer import DisownTimer


class Worker(object):

    # heartbeat_timeout should be passed to the worker as
    # it's configured in a profile.
    # Although runtime replies to heartbeat ASAP, in v0.11
    # ioloop can be blocked for a long period of time, i.e. when
    # docker container is being pulled by engine.
    # Morever a disconnection from runtime can be detected by
    # reading zero bytes from UNIX socket (endpoint).
    def __init__(self, init_args=None, disown_timeout=10, heartbeat_timeout=20):
        self._logger = core_log
        self._init_endpoint(init_args or sys.argv)

        self.sessions = dict()
        self.sandbox = Sandbox()

        self.loop = ev.Loop()

        self.disown_timer = ev.Timer(self.on_disown, disown_timeout, self.loop)
        self.heartbeat_timer = ev.Timer(self.on_heartbeat, heartbeat_timeout, self.loop)

        # it's a fallback mechanism to track
        # that we are disowned even when the main thread is blocked
        # 42 is the universal answer. It's the fallback mechanism
        self.threaded_disown_timer = DisownTimer(disown_timeout * 42)

        if isinstance(self.endpoint, types.TupleType) or isinstance(self.endpoint, types.ListType):
            if len(self.endpoint) == 2:
                socket_type = socket.AF_INET
            elif len(self.endpoint) == 4:
                socket_type = socket.AF_INET6
            else:
                raise ValueError('invalid endpoint')
        elif isinstance(self.endpoint, types.StringType):
            socket_type = socket.AF_UNIX
        else:
            raise ValueError('invalid endpoint')
        sock = socket.socket(socket_type)
        self.pipe = Pipe(sock)
        self.pipe.connect(self.endpoint, blocking=True)
        self.loop.bind_on_fd(self.pipe.fileno())

        self.decoder = Decoder()
        self.decoder.bind(self.on_message)

        self.w_stream = WritableStream(self.loop, self.pipe)
        self.r_stream = ReadableStream(self.loop, self.pipe)
        self.r_stream.bind(self.decoder.decode)

        self.loop.register_read_event(self.r_stream._on_event,
                                      self.pipe.fileno())
        self._logger.debug("Worker with %s send handshake" % self.id)

    def _init_endpoint(self, init_args):
        try:
            self.id = init_args[init_args.index("--uuid") + 1]
            # app_name = init_args[init_args.index("--app") + 1]
            self.endpoint = init_args[init_args.index("--endpoint") + 1]
        except Exception as err:
            self._logger.error("Wrong cmdline arguments: %s " % err)
            raise RuntimeError("Wrong cmdline arguments")

    def run(self, binds=None):
        if not binds:
            binds = {}
        for event, name in binds.iteritems():
            self.on(event, name)
        # Run successfully
        self._send_handshake()
        # Ready to work
        self._send_heartbeat()

        self.heartbeat_timer.start()
        self.threaded_disown_timer.start()
        self.loop.run()

    def terminate(self, reason, msg):
        self.w_stream.write(Message(message.RPC_TERMINATE, 0, reason, msg).pack())
        self.threaded_disown_timer.stop()
        self.loop.stop()
        exit(1)

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

        elif msg.id == message.RPC_INVOKE:
            request = Request()
            stream = Stream(msg.session, self, msg.event)
            try:
                self.sandbox.invoke(msg.event, request, stream)
                self.sessions[msg.session] = request
            except (ImportError, SyntaxError) as err:
                stream.error(2, "unrecoverable error: %s " % str(err))
                self.terminate(1, "Bad code")
            except Exception as err:
                self._logger.error("On invoke error: %s %s" % (err, traceback.format_exc()))
                traceback.print_stack()
                stream.error(1, "Invocation error")

        elif msg.id == message.RPC_CHUNK:
            self._logger.debug("Receive chunk: %d" % msg.session)
            try:
                _session = self.sessions[msg.session]
                _session.push(msg.data)
            except Exception as err:
                self._logger.error("On push error: %s %s" % (err, traceback.format_exc()))
                self.terminate(1, "Push error: %s" % str(err))
                return

        elif msg.id == message.RPC_CHOKE:
            self._logger.debug("Receive choke: %d" % msg.session)
            _session = self.sessions.get(msg.session, None)
            if _session is not None:
                _session.close()
                self.sessions.pop(msg.session)

        elif msg.id == message.RPC_HEARTBEAT:
            self._logger.debug("Receive heartbeat. Stop disown timer")
            self.threaded_disown_timer.notify()
            self.disown_timer.stop()

        elif msg.id == message.RPC_TERMINATE:
            self._logger.debug("Receive terminate. %s, %s" % (msg.reason, msg.message))
            self.terminate(msg.reason, msg.message)

        elif msg.id == message.RPC_ERROR:
            _session = self.sessions.get(msg.session, None)
            if _session is not None:
                _session.error(RequestError(msg.message))

    def on_disown(self):
        try:
            self._logger.error("Disowned")
        finally:
            self.loop.stop()

    # Private:
    def _send_handshake(self):
        self.w_stream.write(Message(message.RPC_HANDSHAKE, 0, self.id).pack())

    def _send_heartbeat(self):
        self.disown_timer.start()
        self._logger.debug("Send heartbeat. Start disown timer")
        self.w_stream.write(Message(message.RPC_HEARTBEAT, 0).pack())

    def send_choke(self, session):
        self.w_stream.write(Message(message.RPC_CHOKE, session).pack())

    def send_chunk(self, session, data):
        self.w_stream.write(Message(message.RPC_CHUNK, session, data).pack())

    def send_error(self, session, code, msg):
        self.w_stream.write(Message(message.RPC_ERROR, session, code, msg).pack())
