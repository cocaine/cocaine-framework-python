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

import sys
from functools import partial

from tornado.ioloop import IOLoop

import msgpack


if sys.version_info[0] == 2:
    msgpack_packb = msgpack.packb
    msgpack_unpackb = msgpack.unpackb
    msgpack_unpacker = msgpack.Unpacker
else:
    # py3: msgpack by default unpacks strings as bytes.
    # Make it to unpack as strings for compatibility.
    msgpack_packb = msgpack.packb
    msgpack_unpackb = partial(msgpack.unpackb, encoding="utf8")
    msgpack_unpacker = partial(msgpack.Unpacker, encoding="utf8")


def get_current_ioloop(loop):
    return loop or IOLoop.current(instance=False) or IOLoop.IOLoop()
