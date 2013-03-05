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

from _proxy import _Proxy

class _HTTPResponse(object):

    def __init__(self, stream):
        self._stream = stream

    def write(self, body):
        self._stream.push(msgpack.packb(body))

    def write_head(self, code, headers):
        self._stream.push(msgpack.packb({'code': code, 'headers' : headers.items()}))

    def close(self):
        self._stream.close()

class ProxyHTTP(_Proxy):
    """ Simple HTTP-wrapper """

    def __init__(self, func, *args, **kwargs):
        self._response = None
        self._obj = func
        self._func = None
        self._state = None

    def __call__(self, chunk):
        try:
            self._func.send(chunk)
        except StopIteration:
            if not self._response.closed:
                self._response.close()

    def push(self, chunk):
        self.__call__(chunk)

    def invoke(self, stream):
        """ stream - object for pushed reponces to the cloud """
        self._state = 1
        self._response = _HTTPResponse(stream) # attach response stream

        self._func = self._obj(self._response) # prepare generator
        self._func.next()

        return self

    def close(self):
        self._state = None

    @property
    def closed(self):
        return self._state is None
