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

from cocaine import concurrent
from cocaine.services import Service
from cocaine.testing.mocks import RuntimeMock, Chunk, Choke

__author__ = 'Evgeny Safronov <division494@gmail.com>'


log = logging.getLogger('cocaine')
h = logging.StreamHandler(stream=sys.stdout)
log.addHandler(h)
log.setLevel(logging.DEBUG)
log.propagate = False


class ServiceTestCase(unittest.TestCase):
    def test_single_chunk(self):
        runtime = RuntimeMock()
        runtime.register('node', 10054, 1, {0: 'list'})
        runtime.when('node').invoke(0).answer([
            Chunk(['echo']),
            Choke()
        ])
        runtime.start()

        @concurrent.engine
        def test():
            actual = yield node.list()
            self.assertEqual(['echo'], actual)
            IOLoop.current().stop()

        node = Service('node')
        test()
        IOLoop.current().start()
        runtime.stop()
