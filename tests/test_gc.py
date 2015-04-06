#
#    Copyright (c) 2012+ Anton Tyurin <noxiouz@yandex.ru>
#    Copyright (c) 2013+ Evgeny Safronov <division494@gmail.com>
#    Copyright (c) 2011-2014 Other contributors as noted in the AUTHORS file.
#
#    This file is part of Cocaine.
#
#    Cocaine is free software; you can redistribute it and/or modify
#    it under the terms of the GNU Lesser General Public License as published by
#    the Free Software Foundation; either version 3 of the License, or
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

import gc
import weakref

from tornado.ioloop import IOLoop

from cocaine.services import Service

io = IOLoop.current()


def test_ref_count_of_service():
    s = Service("storage")
    ws = weakref.ref(s)
    io.run_sync(s.connect, timeout=2)
    wpipe = weakref.ref(s.pipe)
    fd = wpipe().fileno().fileno()
    s = None
    gc.collect()
    # there should be no referres to the service
    assert ws() is None, gc.get_referrers(ws())
    assert fd not in io._handlers, "%d %s" % (fd, io._handlers)
