#
#    Copyright (c) 2011-2013 Anton Tyurin <noxiouz@yandex.ru>
#    Copyright (c) 2011-2013 Other contributors as noted in the AUTHORS file.
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

import posix
import msgpack

from ..server._wrappers import proxy_factory


__all__ = ['fs']


def fs_request_decorator(obj):
    def dec(func):
        def _stat_request_handler(chunk):
            return func(posix.stat_result(msgpack.unpackb(chunk)))
        return _stat_request_handler
    obj.push = dec(obj.push)
    return obj


def fs(func):
    return proxy_factory(func, request_handler=fs_request_decorator)
