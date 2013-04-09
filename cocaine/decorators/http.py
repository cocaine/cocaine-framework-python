# encoding: utf-8
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

import msgpack

from _callablewrappers import proxy_factory

__all__ = ["http"]

class _HTTPResponse(object):

    def __init__(self, stream):
        self._stream = stream

    def write(self, body):
        self._stream.write(msgpack.packb(body))

    def write_head(self, code, headers):
        self._stream.write(msgpack.packb({'code': code, 'headers' : headers}))

    def close(self):
        self._stream.close()

    @property
    def closed(self):
        return self._stream.closed

def http(func):
    return proxy_factory(func, response_handler=_HTTPResponse)
