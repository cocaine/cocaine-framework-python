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

from tornado.ioloop import IOLoop

from cocaine.services import Service
from cocaine.detail.api import API


def test_verify_locator_api():
    io = IOLoop.current()
    l = Service("locator")
    io.run_sync(l.connect)
    assert l.api == API.Locator, "%s\n%s" % (API.Locator, l.api)


def test_verify_logger_api():
    io = IOLoop.current()
    l = Service("logging")
    io.run_sync(l.connect)
    assert l.api == API.Logger, "%s\n%s" % (API.Logger, l.api)
