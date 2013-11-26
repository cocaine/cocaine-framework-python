#
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

import contextlib
import logging
import socket
import sys

from mockito import when, unstub

from tornado import stack_context
from tornado.iostream import IOStream
from cocaine.services.base import ServiceConnector, TimeoutError, ConnectError

from tornado.tcpserver import TCPServer
from tornado.testing import AsyncTestCase

__author__ = 'Evgeny Safronov <division494@gmail.com>'


class SocketServerMock(object):
    def __init__(self):
        self.actions = {
            'connected': lambda: None
        }

        self.connections = {}

    def start(self, port):
        self.server = TCPServer()
        self.server.handle_stream = self._handle_stream
        self.server.listen(port)

    def stop(self):
        self.server.stop()

    def on_connect(self, action):
        self.actions['connected'] = action

    def _handle_stream(self, stream, address):
        self.actions['connected']()
        self.connections[address] = stream


@contextlib.contextmanager
def serve(port):
    server = SocketServerMock()
    try:
        server.start(port)
        yield server
    finally:
        server.stop()


log = logging.getLogger('cocaine')
h = logging.StreamHandler(stream=sys.stdout)
log.addHandler(h)
log.setLevel(logging.DEBUG)
log.propagate = False


class ConnectorTestCase(AsyncTestCase):
    def tearDown(self):
        unstub()

    def test_connect(self):
        def on_connect(future):
            stream = future.get()
            self.assertIsInstance(stream, IOStream)
            self.stop()

        with serve(60000):
            connector = ServiceConnector('localhost', 60000, io_loop=self.io_loop)
            deferred = connector.connect()
            deferred.add_callback(stack_context.wrap(on_connect))
            self.wait()

    def test_consequentially_connect(self):
        def on_connect(future):
            stream = future.get()
            self.assertIsInstance(stream, IOStream)
            self.stop()

        with serve(60000):
            when(socket).getaddrinfo('localhost', 60000, 0, socket.SOCK_STREAM).thenReturn([
                (30, 1, 6, '', ('::1', 59999, 0, 0)),
                (30, 1, 6, '', ('::1', 60000, 0, 0))
            ])

            connector = ServiceConnector('localhost', 60000, io_loop=self.io_loop)
            deferred = connector.connect()
            deferred.add_callback(stack_context.wrap(on_connect))
            self.wait()

    def test_throws_timeout_error_when_connection_timeout(self):
        def on_connect(future):
            self.assertRaises(TimeoutError, future.get)
            self.stop()

        with serve(60000):
            connector = ServiceConnector('localhost', 60000, timeout=0.000001, io_loop=self.io_loop)
            deferred = connector.connect()
            deferred.add_callback(stack_context.wrap(on_connect))
            self.wait()

    def test_throws_error_when_cannot_connect(self):
        def on_connect(future):
            self.assertRaises(ConnectError, future.get)
            self.stop()

        connector = ServiceConnector('localhost', 60000, io_loop=self.io_loop)
        deferred = connector.connect()
        deferred.add_callback(stack_context.wrap(on_connect))
        self.wait()

    def test_allow_multiple_invocation_of_connect_method(self):
        def on_connect(future):
            stream = future.get()
            self.assertIsInstance(stream, IOStream)
            self.stop()

        with serve(60000):
            connector = ServiceConnector('localhost', 60000, io_loop=self.io_loop)
            deferred = connector.connect()
            deferred_2 = connector.connect()
            deferred_3 = connector.connect()
            deferred.add_callback(stack_context.wrap(on_connect))
            self.assertEqual(deferred, deferred_2)
            self.assertEqual(deferred, deferred_3)
            self.wait()