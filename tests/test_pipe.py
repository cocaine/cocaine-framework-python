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

import fcntl
import os
import socket
import unittest

from tornado.ioloop import IOLoop

__author__ = 'Evgeny Safronov <division494@gmail.com>'


class Pipe(object):
    def __init__(self, sock, io_loop=None):
        self.sock = sock
        self.sock.setblocking(False)
        self.io_loop = io_loop


class PipeTestCase(unittest.TestCase):
    def test_class(self):
        Pipe(socket.socket())
        Pipe(socket.socket(), IOLoop.current())

    def test_transforms_socket_into_non_blocking(self):
        sock = socket.socket()
        Pipe(sock)
        self.assertTrue(fcntl.fcntl(sock.fileno(), fcntl.F_GETFL) & os.O_NONBLOCK)

    def test_can_connect_to_socket(self):
        self.fail()

    def test_throws_exception_on_fail_to_connect_to_socket_sync(self):
        self.fail()

    def test_can_connect_to_socket_async(self):
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