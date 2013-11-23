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
import sys
import unittest

from tornado.ioloop import IOLoop
from tornado.testing import AsyncTestCase

from cocaine import concurrent
from cocaine.services import Service
from cocaine.testing.mocks import RuntimeMock, Chunk, Choke

__author__ = 'Evgeny Safronov <division494@gmail.com>'


log = logging.getLogger('cocaine')
h = logging.StreamHandler(stream=sys.stdout)
log.addHandler(h)
log.setLevel(logging.DEBUG)
log.propagate = False


class RuntimeTestCase(AsyncTestCase):
    def setUp(self):
        super(RuntimeTestCase, self).setUp()
        self.runtime = self.get_runtime()

    def tearDown(self):
        super(RuntimeTestCase, self).tearDown()
        self.runtime.stop()

    def get_runtime(self):
        return RuntimeMock(io_loop=IOLoop())


class ServiceTestCase(RuntimeTestCase):
    def test_single_chunk(self):
        self.runtime.register('node', 10054, 1, {0: 'list'})
        self.runtime.when('node').invoke(0).answer([
            Chunk(['echo']),
            Choke()
        ])
        self.runtime.start()

        @concurrent.engine
        def test():
            actual = yield node.list()
            self.assertEqual(['echo'], actual)
            self.stop()

        node = Service('node')
        test()
        self.wait()

    def test_single_chunk2(self):
        self.runtime.register('node', 10054, 1, {0: 'list'})
        self.runtime.when('node').invoke(0).answer([
            Chunk(['echo']),
            Choke()
        ])
        self.runtime.start()

        @concurrent.engine
        def test():
            actual = yield node.list()
            self.assertEqual(['echo'], actual)
            self.stop()

        node = Service('node')
        test()
        self.wait()
