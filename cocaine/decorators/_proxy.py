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

from abc import ABCMeta, abstractmethod

class _Proxy(object):

    __metaclass__ = ABCMeta

    _wrapped =True

    @abstractmethod
    def __init__(self, func, *args, **kwargs):
        pass

    @abstractmethod
    def __call__(self, *args):
        pass

    @abstractmethod
    def push(self, chunk):
        pass

    @abstractmethod
    def invoke(self, stream):
        pass

    @abstractmethod
    def close(self):
        pass

    @property
    def closed(self):
        return self._state is None
