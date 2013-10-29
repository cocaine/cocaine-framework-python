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

import threading
import types
import weakref


class weakmethod(object):
    __slots__ = ['func']

    def __init__(self, func):
        self.func = func

    def __get__(self, obj, cls):
        if obj is not None:
            obj = weakref.proxy(obj)
        return types.MethodType(self.func, obj, cls)


class ThreadLocalMixin(object):
    __instance_lock = threading.Lock()
    __instance = None
    __current = threading.local()

    @classmethod
    def instance(cls):
        if not cls.__instance:
            with cls.__instance_lock:
                if not cls.__instance:
                    cls.__instance = cls()
        return cls.__instance

    @classmethod
    def current(cls):
        current = getattr(cls.__current, 'instance', None)
        if current is None:
            return cls.instance()
        return current