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
import sys
import time

from tornado import stack_context
from tornado.ioloop import IOLoop
from tornado.tcpserver import TCPServer
from tornado.testing import AsyncTestCase
from cocaine.concurrent import Deferred

__author__ = 'Evgeny Safronov <division494@gmail.com>'


handler = logging.StreamHandler(sys.stdout)
log = logging.getLogger(__name__)
log.addHandler(handler)
log.setLevel(logging.DEBUG)
log.propagate = False


class PipeError(Exception):
    pass


class TimeoutError(PipeError):
    pass


def add_timeout_watcher(func, timeout, callback, io_loop):
    if timeout is None:
        return func

    timeout_id = io_loop.add_timeout(time.time() + timeout, callback)

    def wrapper(*args, **kwargs):
        io_loop.remove_timeout(timeout_id)
        func(*args, **kwargs)
    return wrapper


class Pipe(object):
    CLOSED, CONNECTING, CONNECTED = range(3)

    def __init__(self, sock, io_loop):
        self.sock = sock
        self.sock.setblocking(False)
        self.io_loop = io_loop or IOLoop.current()

        self._connected_callback = None

        self._connect_deferred = None
        self._connect_timeout = None
        self._connect_timeout_id = None

        self._state = self.CLOSED
        self._events = None

    @property
    def state(self):
        return self._state

    @property
    def closed(self):
        return self._state == self.CLOSED

    @property
    def connecting(self):
        return self._state == self.CONNECTING

    @property
    def connected(self):
        return self._state == self.CONNECTED

    def connect(self, address, timeout=None):
        if self.connecting:
            return self._connect_deferred

        self._connect_deferred = Deferred()
        self._state = self.CONNECTING
        self._connect(address, timeout)
        return self._connect_deferred

    def _connect(self, address, timeout):
        try:
            log.debug('connecting to the %s', address)
            self.sock.connect(address)
        except socket.error as err:
            if err.errno in (errno.EINPROGRESS, errno.EWOULDBLOCK):
                if timeout:
                    self._connected_callback = add_timeout_watcher(
                        self._handle_connect, timeout, self._handle_connect_timeout, self.io_loop)
                else:
                    self._connected_callback = self._handle_connect
                self._add_io_state(self.io_loop.WRITE)
            else:
                log.warn('connect error on fd %d: %s', self.sock.fileno(), err)
                self._connect_deferred.error(PipeError(''))
                self._connect_deferred = None
                self.close()
                return

    def set_nodelay(self, value):
        if self.sock is not None and self.sock.family in (socket.AF_INET, socket.AF_INET6):
            try:
                self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1 if value else 0)
            except socket.error as err:
                if err.errno != errno.EINVAL:
                    raise

    def _add_io_state(self, event):
        if self.closed:
            return

        if self._events is None:
            self._events = event | IOLoop.ERROR
            with stack_context.NullContext():
                self.io_loop.add_handler(self.fileno(), self._handle_events, self._events)
        elif not event & self._events:
            self._events |= event
            self.io_loop.update_handler(self.fileno(), self._events)

    def _handle_events(self, fd, events):
        if self.closed:
            log.warn('got events for closed stream %d', fd)
            return

        try:
            if events & IOLoop.READ:
                self._handle_read()
            if self.closed:
                return

            if self.connecting:
                if (events & IOLoop.WRITE) | (events & IOLoop.ERROR):
                    self._connected_callback()

            if events & IOLoop.WRITE:
                self._handle_write()
            if self.closed:
                return

            if events & IOLoop.ERROR:
                self.error = self.get_fd_error()
                self.io_loop.add_callback(self.close)
                return

            event = IOLoop.ERROR
            # if self.reading():
            #     event |= IOLoop.READ
            # if self.writing():
            #     event |= IOLoop.WRITE
            if event == IOLoop.ERROR:
                event |= IOLoop.READ
            if event != self._state:
                self._events = event
                self.io_loop.update_handler(self.fileno(), self._events)
        except Exception:
            log.error('uncaught exception, closing connection', exc_info=True)
            # self.close(exc_info=True)
            # raise

    def _handle_connect(self):
        log.debug('handling connect for %d', self.sock.fileno())
        err = self.sock.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
        if err == 0:
            self._state = self.CONNECTED
            self._connect_deferred.trigger()
        else:
            log.warn('connect error on fd %d: %s', self.sock.fileno(), errno.errorcode[err])
            self._connect_deferred.error(PipeError(''))
            self._connect_deferred = None
            self.close()

    def _handle_connect_timeout(self):
        log.warn('connect error on fd %d: %s', self.sock.fileno(), 'timeout')
        self._connect_deferred.error(TimeoutError(''))
        self._connect_deferred = None
        self.close()

    def close(self):
        self._state = self.CLOSED

    def fileno(self):
        return self.sock.fileno()

    def _handle_read(self):
        pass

    def _handle_write(self):
        pass

    def get_fd_error(self):
        errno = self.sock.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
        return socket.error(errno, os.strerror(errno))


class SocketServerMock(object):
    def __init__(self):
        self.actions = {
            'connected': lambda: None
        }

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


@contextlib.contextmanager
def serve(port):
    server = SocketServerMock()
    try:
        server.start(port)
        yield server
    finally:
        server.stop()


class CommonPipeTestCase(AsyncTestCase):
    def test_class(self):
        Pipe(socket.socket(), self.io_loop)
        Pipe(socket.socket(), IOLoop.current())

    def test_transforms_socket_into_non_blocking(self):
        sock = socket.socket()
        Pipe(sock, self.io_loop)
        self.assertTrue(fcntl.fcntl(sock.fileno(), fcntl.F_GETFL) & os.O_NONBLOCK)

    def test_can_make_socket_no_delay(self):
        sock = socket.socket()
        pipe = Pipe(sock, self.io_loop)
        pipe.set_nodelay(True)
        self.assertTrue(sock.getsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY))


class AsynchronousPipeTestCase(AsyncTestCase):
    os.environ.setdefault('ASYNC_TEST_TIMEOUT', '0.5')

    def test_can_connect_to_remote_address(self):
        with serve(60000) as server:
            pipe = Pipe(socket.socket(), self.io_loop)
            pipe.connect(('127.0.0.1', 60000))
            server.on_connect(self.stop)
            self.wait()

    def test_returns_deferred_when_connecting(self):
        pipe = Pipe(socket.socket(), self.io_loop)
        deferred = pipe.connect(('127.0.0.1', 60000))
        self.assertTrue(isinstance(deferred, Deferred))

    def test_has_disconnected_state_by_default(self):
        pipe = Pipe(socket.socket(), self.io_loop)
        self.assertEqual(Pipe.CLOSED, pipe.state)
        self.assertTrue(pipe.closed)

    def test_has_connecting_state_while_connecting(self):
        pipe = Pipe(socket.socket(), self.io_loop)
        pipe.connect(('127.0.0.1', 60000))
        self.assertEqual(Pipe.CONNECTING, pipe.state)
        self.assertTrue(pipe.connecting)

    def test_has_disconnected_state_after_closed(self):
        self.fail()

    def test_has_disconnected_state_after_error(self):
        self.fail()

    def test_has_disconnected_state_after_connecting_error(self):
        self.fail()

    def test_can_connect_to_socket_async_multiple_times(self):
        pipe = Pipe(socket.socket(), self.io_loop)
        deferred = pipe.connect(('127.0.0.1', 60000))
        self.assertEqual(deferred, pipe.connect(()))

    def test_triggers_connect_deferred_when_connected(self):
        flag = [0]

        def on_client_connect(future):
            flag[0] += 1
            self.assertIsNone(future.get())
            if flag[0] == 2:
                self.stop()

        def on_server_connect():
            flag[0] += 1
            if flag[0] == 2:
                self.stop()

        with serve(60000) as server:
            pipe = Pipe(socket.socket(), self.io_loop)
            deferred = pipe.connect(('127.0.0.1', 60000))
            deferred.add_callback(stack_context.wrap(on_client_connect))
            server.on_connect(stack_context.wrap(on_server_connect))
            self.wait()

        self.assertEqual(2, flag[0])
        self.assertEqual(Pipe.CONNECTED, pipe.state)
        self.assertTrue(pipe.connected)

    def test_triggers_connect_deferred_when_timeout(self):
        flag = [False]

        def on_client_connect(future):
            flag[0] = True
            self.assertRaises(TimeoutError, future.get)
            self.stop()

        with serve(60000):
            pipe = Pipe(socket.socket(), self.io_loop)
            deferred = pipe.connect(('127.0.0.1', 60000), timeout=0.000001)
            deferred.add_callback(stack_context.wrap(on_client_connect))
            self.wait()
        self.assertTrue(flag[0])

    def test_triggers_connect_deferred_when_error(self):
        flag = [False]

        def on_client_connect(future):
            flag[0] = True
            self.assertRaises(PipeError, future.get)
            self.stop()

        pipe = Pipe(socket.socket(), self.io_loop)
        deferred = pipe.connect(('127.0.0.1', 60000))
        deferred.add_callback(on_client_connect)
        self.wait()
        self.assertTrue(flag[0])

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