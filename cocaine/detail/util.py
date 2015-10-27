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

import hashlib
import sys
import time
from functools import partial

import msgpack


if sys.version_info[0] == 2:
    msgpack_packb = msgpack.packb
    msgpack_unpackb = msgpack.unpackb
    msgpack_unpacker = msgpack.Unpacker
else:  # pragma: no cover
    # py3: msgpack by default unpacks strings as bytes.
    # Make it to unpack as strings for compatibility.
    msgpack_packb = msgpack.packb
    msgpack_unpackb = partial(msgpack.unpackb, encoding="utf8")
    msgpack_unpacker = partial(msgpack.Unpacker, encoding="utf8")


if sys.version_info[0] == 2:
    def valid_chunk(chunk):
        return isinstance(chunk, (str, unicode, bytes))

    def generate_service_id(self):
        return hashlib.md5("%d:%f" % (id(self), time.time())).hexdigest()[:15]
else:
    def valid_chunk(chunk):
        return isinstance(chunk, (str, bytes))

    def generate_service_id(self):
        hashed = "%d:%f" % (id(self), time.time())
        return hashlib.md5(hashed.encode("utf-8")).hexdigest()[:15]
