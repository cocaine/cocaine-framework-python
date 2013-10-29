#
#    Copyright (c) 2011-2013 Anton Tyurin <noxiouz@yandex.ru>
#    Copyright (c) 2013+ Evgeny Safronov <division494@gmail.com>
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

from ..asio import ev
from ..asio.pipe import Pipe
from ..asio.stream import ReadableStream, WritableStream, Decoder
from ..concurrent import Deferred
from ..logging import core as log
from ..protocol.message import Message, RPC

from .request import Request
from .response import Response
from .sandbox import Sandbox


class WorkerConnection(object):
    def __init__(self, endpoint, on_message, io_loop):
        self._io_loop = io_loop

        if isinstance(endpoint, types.TupleType) or isinstance(endpoint, types.ListType):
            if len(endpoint) == 2:
                socket_type = socket.AF_INET
            elif len(endpoint) == 4:
                socket_type = socket.AF_INET6
            else:
                raise ValueError('invalid endpoint')
        elif isinstance(endpoint, types.StringType):
            socket_type = socket.AF_UNIX
        else:
            raise ValueError('invalid endpoint')

        self.pipe = Pipe(socket.socket(socket_type))
        self.pipe.connect(endpoint, blocking=True)
        self._io_loop.bind_on_fd(self.pipe.fileno())

        self.decoder = Decoder()
        self.decoder.bind(on_message)

        self.w_stream = WritableStream(self._io_loop, self.pipe)
        self.r_stream = ReadableStream(self._io_loop, self.pipe)
        self.r_stream.bind(self.decoder.decode)

        self._io_loop.register_read_event(self.r_stream._on_event, self.pipe.fileno())

    def connect(self):
        d = Deferred()
        d.trigger()
        return d

    def send_data(self, data):
        self.w_stream.write(data)


class Timer(object):
    def __init__(self, timeout, callback):
        self.timeout = timeout
        self.callback = callback


class HealthManager(object):
    def __init__(self, disown_timeout, heartbeat_timeout, heartbeat_callback, io_loop):
        self._heartbeat_callback = heartbeat_callback
        self._io_loop = io_loop

        self._disown_timer = ev.Timer(self._on_disown, disown_timeout, self._io_loop)
        self._heartbeat_timer = ev.Timer(self._on_heartbeat, heartbeat_timeout, self._io_loop)

    def start(self):
        self._heartbeat_timer.start()

    def breath(self):
        self._disown_timer.stop()

    def _on_disown(self):
        log.error('disowned')
        self._io_loop.stop()

    def _on_heartbeat(self, session=0):
        self._disown_timer.start()
        self._heartbeat_callback(session)


class Worker(object):
    class TimeoutControl:
        def __init__(self, disown, heartbeat):
            self.disown = disown
            self.heartbeat = heartbeat

    def __init__(self, uuid=None, endpoint=None):
        try:
            self.uuid = uuid or sys.argv[sys.argv.index('--uuid') + 1]
            self.endpoint = endpoint or sys.argv[sys.argv.index('--endpoint') + 1]
        except KeyError:
            raise ValueError('wrong command line arguments: {0}'.format(sys.argv))

        self._io_loop = ev.Loop()

        # Dispatching
        self._sandbox = Sandbox()

        # Health control
        self._health = HealthManager(5.0, 20.0, self._send_heartbeat, self._io_loop)

        # Connection control
        self._sessions = {}
        self._connection = WorkerConnection(self.endpoint, on_message=self._on_message, io_loop=self._io_loop)
        deferred = self._connection.connect()
        deferred.add_callback(self._on_connect)

    def on(self, event, callback):
        self._sandbox.on(event, callback)

    def run(self, binds=None):
        if not binds:
            binds = {}
        for event, name in binds.items():
            self.on(event, name)

        self._io_loop.run()

    def terminate(self, session, errno, reason):
        self._send_terminate(session, errno, reason)
        self._io_loop.stop()
        exit(errno)

    def _on_connect(self, result):
        try:
            result.get()
        except Exception as err:
            log.error('failed to connect worker with cocaine-runtime: %s', err)
        else:
            self._send_handshake()
            self._send_heartbeat()
            self._health.start()

    def _on_message(self, args):
        msg = Message.initialize(args)
        log.debug('[->] %s', msg)
        if msg.id == RPC.HEARTBEAT:
            self._health.breath()
        elif msg.id == RPC.TERMINATE:
            self.terminate(msg.session, msg.errno, msg.reason)
        elif msg.id == RPC.INVOKE:
            deferred = Deferred()
            request = Request(deferred)
            response = Response(msg.session, self)
            try:
                self._sandbox.invoke(msg.event, request, response)
                self._sessions[msg.session] = deferred
            except (ImportError, SyntaxError) as err:
                response.error(2, 'unrecoverable error: %s ' % str(err))
                self.terminate(msg.session, 1, 'Bad code')
            except Exception as err:
                log.error('On invoke error: %s' % err)
                traceback.print_stack()
                response.error(1, 'Invocation error')
        elif msg.id == RPC.CHUNK:
            try:
                deferred = self._sessions[msg.session]
                deferred.trigger(msg.data)
            except Exception as err:
                log.error('On push error: %s' % str(err))
                self.terminate(msg.session, 1, 'Push error: %s' % str(err))
                return
        elif msg.id == RPC.ERROR:
            deferred = self._sessions.get(msg.session, None)
            if deferred is not None:
                deferred.error(Exception(msg.reason))
        elif msg.id == RPC.CHOKE:
            deferred = self._sessions.get(msg.session, None)
            if deferred is not None:
                deferred.close()
                self._sessions.pop(msg.session)

    def _send_handshake(self, session=0):
        log.debug('[<-] handshake')
        self._send(RPC.HANDSHAKE, session, self.uuid)

    def _send_heartbeat(self, session=0):
        log.debug('[<-] heartbeat')
        self._send(RPC.HEARTBEAT, session)

    def _send_terminate(self, session, errno, reason):
        self._send(RPC.TERMINATE, session, errno, reason)

    def _send_choke(self, session):
        self._send(RPC.CHOKE, session)

    def _send_chunk(self, session, data):
        self._send(RPC.CHUNK, session, data)

    def _send_error(self, session, errno, reason):
        self._send(RPC.ERROR, session, errno, reason)

    def _send(self, id_, session, *args):
        self._connection.send_data(Message(id_, session, *args).pack())
