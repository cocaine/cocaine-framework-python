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


class ProxyCoroutine(_Proxy):
    """ Wrapper on coroutine-like function. Call next() for contained object on Invoke.\
        Then call send() method."""

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
        self._state = 1
        self._response = stream
        self._func = self._obj(self._response) # prepare generator
        self._func.next()
        return self

    def close(self):
        self._func.throw(Exception("close"))
        self._state = None
        if not self._response.closed:
            self._response.close()
