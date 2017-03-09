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
from __future__ import unicode_literals

import hashlib
import time
from functools import partial

import msgpack

import six

msgpack_pack = msgpack.pack
msgpack_packb = msgpack.packb
msgpack_unpackb = msgpack.unpackb
msgpack_unpacker = partial(msgpack.Unpacker, use_list=True)


def valid_chunk(chunk):
    return isinstance(chunk, six.string_types + (six.binary_type,))


def generate_service_id(self):
    hashed = "%d:%f" % (id(self), time.time())
    return hashlib.md5(hashed.encode("utf-8")).hexdigest()[:15]
