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
import errno
import fcntl
import logging
import os
import socket
import threading

from tornado.ioloop import IOLoop
from tornado.tcpserver import TCPServer
from tornado.testing import AsyncTestCase
from cocaine.concurrent import Deferred

__author__ = 'Evgeny Safronov <division494@gmail.com>'


log = logging.getLogger(__name__)


class Pipe(object):
    def __init__(self, sock, io_loop=None):
        self.sock = sock
        self.sock.setblocking(False)
        self.io_loop = io_loop

        self._connect_deferred = None

    def connect(self, address, sync=False):
        self._connect_deferred = Deferred()
        if sync:
            self._connect_sync(address)
        else:
            self._connect(address)

        return self._connect_deferred

    def _connect_sync(self, address):
        try:
            self.sock.settimeout(5.0)  # timeout)
            self.sock.connect(address)
            # self._state = self.CONNECTED
        except socket.error as err:
            # if err.errno == errno.ECONNREFUSED:
            #     raise ConnectionRefusedError(address)
            # elif err.errno == errno.ETIMEDOUT:
            #     raise ConnectionTimeoutError(address, timeout)
            # else:
            #     raise ConnectionError(address, err)
            pass
        finally:
            self.sock.setblocking(False)

    def _connect(self, address):
        try:
            self.sock.connect(address)
        except socket.error as err:
            if err.errno not in (errno.EINPROGRESS, errno.EWOULDBLOCK):
                log.warn('connect error on fd %d: %s', self.sock.fileno(), err)


class SocketServerMock(object):
    def __init__(self):
        self.thread = None
        self.lock = threading.Lock()
        self.started = threading.Event()
        self.actions = {}

    def start(self, port):
        self.thread = threading.Thread(target=self._start, args=(port,))
        self.thread.start()
        self.started.wait()

    def stop(self):
        if self.thread:
            self.io_loop.stop()
            self.thread.join()

    def on_connect(self, action):
        with self.lock:
            self.actions['connected'] = action

    def _start(self, port):
        self.io_loop = IOLoop()
        self.io_loop.make_current()
        server = TCPServer(self.io_loop)
        server.handle_stream = self._handle_stream
        server.listen(port)
        self.io_loop.add_callback(self.started.set)
        self.io_loop.start()
        server.stop()

    def _handle_stream(self, stream, address):
        with self.lock:
            self.actions['connected']()


@contextlib.contextmanager
def serve(port):
    server = SocketServerMock()
    try:
        server.start(port)
        yield server
    finally:
        server.stop()


class PipeTestCase(AsyncTestCase):
    os.environ.setdefault('ASYNC_TEST_TIMEOUT', '0.5')

    def test_class(self):
        Pipe(socket.socket())
        Pipe(socket.socket(), IOLoop.current())

    def test_transforms_socket_into_non_blocking(self):
        sock = socket.socket()
        Pipe(sock)
        self.assertTrue(fcntl.fcntl(sock.fileno(), fcntl.F_GETFL) & os.O_NONBLOCK)

    def test_can_connect_to_remote_address_sync(self):
        flag = [False]

        def set_flag():
            flag[0] = True

        with serve(60000) as server:
            pipe = Pipe(socket.socket(), self.io_loop)
            pipe.connect(('127.0.0.1', 60000), sync=True)
            server.on_connect(set_flag)

        self.assertTrue(flag[0])

    def test_can_make_socket_no_delay(self):
        self.fail()

    def test_throws_exception_on_fail_to_connect_to_socket_sync(self):
        self.fail()

    def test_can_connect_to_remote_address_async(self):
        with serve(60000) as server:
            pipe = Pipe(socket.socket(), self.io_loop)
            pipe.connect(('127.0.0.1', 60000))
            server.on_connect(self.stop)
            self.wait()

    def test_returns_deferred_when_connected_async(self):
        self.fail()

    def test_has_disconnected_state_by_default(self):
        self.fail()

    def test_has_connected_state_after_connected(self):
        self.fail()

    def test_has_connecting_state_while_connecting(self):
        self.fail()

    def test_has_disconnected_state_after_closed(self):
        self.fail()

    def test_has_disconnected_state_after_error(self):
        self.fail()

    def test_has_disconnected_state_after_connecting_error(self):
        self.fail()

    def test_can_connect_to_socket_async_multiple_times(self):
        self.fail()

    def test_triggers_connect_deferred_when_connected(self):
        self.fail()

    def test_triggers_connect_deferred_when_timeout(self):
        self.fail()

    def test_triggers_connect_deferred_when_error(self):
        self.fail()

    def test_calls_callback_on_close(self):
        self.fail()

    def test_writes_to_socket_correctly(self):
        self.fail()

    def test_reads_from_socket_correctly(self):
        self.fail()

    def test_calls_callback_on_read_event(self):
        self.fail()

    def test_calls_callback_on_write_event(self):
        self.fail()

    def test_throws_exception_on_write_fail(self):
        self.fail()

    def test_throws_exception_on_read_fail(self):
        self.fail()