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

import logging
import socket
import msgpack

from tornado.testing import AsyncTestCase

from cocaine.asio.stream import CocaineStream
from cocaine.testing.mocks import serve

__author__ = 'Evgeny Safronov <division494@gmail.com>'


log = logging.getLogger('cocaine')


class StreamTestCase(AsyncTestCase):
    def test_can_connect(self):
        with serve(60000):
            stream = CocaineStream(socket.socket(), self.io_loop)
            stream.connect(('127.0.0.1', 60000))
            self.assertFalse(stream.closed())
            self.assertTrue(stream.connecting())
            self.assertFalse(stream.connected())

    def test_triggers_close_callback_when_closed(self):
        def on_closed():
            self.stop()

        def on_connect():
            server.stop()

        with serve(60000) as server:
            stream = CocaineStream(socket.socket(), self.io_loop)
            stream.connect(('127.0.0.1', 60000), on_connect)
            stream.set_close_callback(on_closed)
            self.wait()

    def test_triggers_on_message_callback_with_message(self):
        def on_message(message):
            self.assertEqual([4, 1, ['name']], message)
            self.stop()

        def on_connect():
            server.connections[stream.address()].write(msgpack.dumps([4, 1, ['name']]))

        with serve(60000) as server:
            stream = CocaineStream(socket.socket(), self.io_loop)
            stream.connect(('127.0.0.1', 60000))
            server.on_connect(on_connect)
            stream.set_read_callback(on_message)
            self.wait()
