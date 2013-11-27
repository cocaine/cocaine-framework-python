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
import types

from tornado.ioloop import PeriodicCallback, IOLoop

from ..asio.stream import CocaineStream
from ..concurrent import Deferred
from ..logging.defaults import core as log
from ..protocol.message import Message, RPC

from .request import Request
from .response import Response
from .sandbox import Sandbox


class WorkerConnection(object):
    def __init__(self, endpoint, io_loop):
        self.endpoint = endpoint
        self._stream = CocaineStream(self.create_socket(endpoint), io_loop=io_loop)
        self._connect_deferred = Deferred()

    @staticmethod
    def create_socket(endpoint):
        if isinstance(endpoint, types.TupleType) or isinstance(endpoint, types.ListType):
            if len(endpoint) == 2:
                family = socket.AF_INET
            elif len(endpoint) == 4:
                family = socket.AF_INET6
            else:
                raise ValueError('invalid endpoint')
        elif isinstance(endpoint, types.StringType):
            family = socket.AF_UNIX
        else:
            raise ValueError('invalid endpoint')
        return socket.socket(family)

    def connect(self):
        self._stream.connect(self.endpoint, callback=self._on_connect)
        return self._connect_deferred

    def _on_connect(self):
        self._connect_deferred.trigger()

    def send_data(self, data):
        self._stream.write(data)

    def set_read_callback(self, callback):
        self._stream.set_read_callback(callback)


class Timer(object):
    def __init__(self, timeout, callback):
        self.timeout = timeout
        self.callback = callback


class HealthManager(object):
    def __init__(self, disown_timeout, heartbeat_timeout, heartbeat_callback, io_loop):
        self._heartbeat_callback = heartbeat_callback
        self._io_loop = io_loop

        self._disown_timer = PeriodicCallback(self._on_disown, 1000 * disown_timeout, self._io_loop)
        self._heartbeat_timer = PeriodicCallback(self._on_heartbeat, 1000 * heartbeat_timeout, self._io_loop)

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

        self._io_loop = IOLoop.current()

        # Dispatching
        self._sandbox = Sandbox()
        self._dispatcher = {
            RPC.HEARTBEAT: self._dispatch_heartbeat,
            RPC.TERMINATE: self._dispatch_terminate,
            RPC.INVOKE: self._dispatch_invoke,
            RPC.CHUNK: self._dispatch_chunk,
            RPC.ERROR: self._dispatch_error,
            RPC.CHOKE: self._dispatch_choke
        }

        # Health control
        self._health = HealthManager(5.0, 20.0, self._send_heartbeat, self._io_loop)

        # Connection control
        self._sessions = {}
        self._connection = WorkerConnection(self.endpoint, io_loop=self._io_loop)
        deferred = self._connection.connect()
        deferred.add_callback(self._on_connect)

    def on(self, event, callback):
        self._sandbox.on(event, callback)

    def run(self, binds=None):
        if not binds:
            binds = {}
        for event, name in binds.items():
            self.on(event, name)

        self._io_loop.start()

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
            self._connection.set_read_callback(self._dispatch)
            self._send_handshake()
            self._send_heartbeat()
            self._health.start()

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

    def _dispatch(self, data):
        message = Message.initialize(data)
        log.debug('[->] %s', message)
        assert message.id in self._dispatcher, 'unexpected message: {0}'.format(message.id)
        log.debug('dispatching %s', message)
        dispatch = self._dispatcher[message.id]
        dispatch(message)

    def _dispatch_heartbeat(self, message):
        self._health.breath()

    def _dispatch_terminate(self, message):
        self._send_terminate(message.session, message.errno, message.reason)

    def _dispatch_invoke(self, message):
        deferred = Deferred()
        request = Request(deferred)
        response = Response(message.session, self)
        try:
            self._sandbox.invoke(message.event, request, response)
            self._sessions[message.session] = deferred
        except (ImportError, SyntaxError) as err:
            response.error(2, 'unrecoverable error: %s ', err)
            self._send_terminate(message.session, 1, 'programming error')
        except Exception as err:
            log.error('on invoke error: %s', err, print_exc=True)
            response.error(1, 'invocation error')

    def _dispatch_chunk(self, message):
        log.debug('receive chunk: %d', message.session)
        try:
            deferred = self._sessions[message.session]
            deferred.trigger(message.data)
        except Exception as err:
            log.error('push error: %s', err)
            self._send_terminate(message.session, 1, 'push error: {0}'.format(err))

    def _dispatch_error(self, message):
        deferred = self._sessions.get(message.session, None)
        if deferred is not None:
            deferred.error(Exception(message.reason))

    def _dispatch_choke(self, message):
        log.debug('receive choke: %d', message.session)
        try:
            deferred = self._sessions.pop(message.session)
            deferred.close()
        except KeyError:
            pass