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

from weakref import proxy
from types import MethodType


class weakmethod(object):
    __slots__ = ["func"]

    def __init__(self, func):
        self.func = func

    def __get__(self, obj, cls):
        if obj is not None:
            obj = proxy(obj)
        return MethodType(self.func, obj, cls)


class Optional(object):
    __slots__ = ['value', '_value', '_is_set']

    def __init__(self):
        self._value = None
        self._is_set = False

    def single(self):
        return self._is_set and self._value is None

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, val):
        self._value = val
        self._is_set = True