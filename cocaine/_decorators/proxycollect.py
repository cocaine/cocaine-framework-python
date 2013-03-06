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

from _proxy import _Proxy

class ProxyCollect(_Proxy):
    """ Collect all chunk to list """

    def __init__(self, func):
        self._response = None
        self._buffer = list()
        self._obj = func

    def __call__(self, chunk):
        self._buffer.append(chunk)

    def invoke(self):
        self._response = cStringIO.StringIO()

    def close(self):
        self._obj(self._buffer, self._response)
        #print self._response.getvalue()
        self._response.close()
        self._buffer = list()
