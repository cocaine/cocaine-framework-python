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

__all__ = ["proxy_factory"]

from abc import ABCMeta, abstractmethod
import compiler

class _Proxy(object):

    __metaclass__ = ABCMeta
    _wrapped = True

    @abstractmethod
    def __init__(self, func): pass

    @abstractmethod
    def invoke(self, stream): pass

    @property
    def closed(self):
        return self._state is None

def exception_trap(func):
    def wrapper(self, *args, **kwargs):
        try:
            func(self, *args, **kwargs)
        except StopIteration:
            if not self._response.closed:
                self._response.close()
        except Exception as err:
            print "Uncaught exception: %s " %  str(err)
    return wrapper


class _Coroutine(_Proxy):
    """Wrapper for coroutine function """

    def __init__(self, func):
        self._response = None
        self._obj = func
        self._func = None
        self._state = None
        self._current_future_object = None

    @exception_trap
    def push(self, chunk):
        self._current_future_object = self._func.send(chunk)
        while self._current_future_object is None:
            self._current_future_object = self._func.next()
        self._current_future_object(self.push, self.error)

    @exception_trap
    def error(self, error):
        self._current_future_object = self._func.throw(error)
        while self._current_future_object is None:
            self._current_future_object = self._func.next()
        self._current_future_object(self.push, self.error)

    def invoke(self, request, stream):
        self._state = 1
        self._response = stream # attach response stream
        self._func = self._obj(request, self._response) # prepare generator
        self._current_future_object = self._func.next()
        if self._current_future_object is not None:
            try:
                self._current_future_object(self.push, self.error)
            except Exception as err:
                print "Invoke error: %s " % str(err)

    def close(self):
        self._state = None

#===========================================

class _Function(_Proxy):
    """Wrapper for function object"""

    def __init__(self, func):
        #self._state = None
        self._func = func
        #self._response = None

    def invoke(self, request, stream):
        self._state = 1
        self._response = stream
        self._request = request
        try:
            self._func(self._request, self._response)
        except Exception as err:
            print str(err)

    def push(self, chunk):
        try:
            self._func(chunk, self._response)
        except Exception as err:
            print str(err)

    def close(self):
        self._state = None

#=========================================


def type_traits(func_or_generator):
    """ Return class object depends on type of callable object """
    if (compiler.consts.CO_GENERATOR & func_or_generator.func_code.co_flags): # Coroutine
        return _Coroutine
    else:
        return _Function

def decomaker(handler):
    def dec(func):
        def wrapper(self, arg):
            return func(self, handler(arg))
        return wrapper
    return dec

def patch_invoke(cls, response_handler):
    cls.invoke = decomaker(response_handler)(cls.invoke)
    return cls

def patch_push(cls, request_handler):
    cls.push = decomaker(request_handler)(cls.push)
    return cls

def proxy_factory(func, request_handler=None, response_handler=None):
    _factory = type_traits(func)
    if response_handler is not None:
        _factory = patch_invoke(_factory, response_handler)
    if request_handler is not None:
        _factory = patch_push(_factory, request_handler)
    return _factory(func)
