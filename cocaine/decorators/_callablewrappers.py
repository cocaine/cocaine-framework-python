# encoding: utf-8
#
#    Copyright (c) 2011-2013 Anton Tyurin <noxiouz@yandex.ru>
#    Copyright (c) 2011-2013 Other contributors as noted in the AUTHORS file.
#
#    This file is part of Cocaine.
#
#    Cocaine is free software; you can redistribute it and/or modify
#    it under the terms of the GNU Lesser General Public License as published
#    by the Free Software Foundation; either version 3 of the License, or
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
import traceback

from cocaine.exceptions import ChokeEvent
from cocaine.logging.log import core_log
from cocaine.futures.chain import Chain


class _Proxy(object):

    __metaclass__ = ABCMeta
    _wrapped = True
    _logger = core_log

    @abstractmethod
    def invoke(self, request, stream):
        pass

    @property
    def closed(self):
        return self._state is None


class _Coroutine(_Proxy):
    """Wrapper for coroutine function """

    def __init__(self, func):
        self._response = None
        self._obj = func
        self._state = None
        self._current_future_object = None

    def invoke(self, request, stream):
        self._state = 1
        self._response = stream  # attach response stream
        Chain([lambda: self._obj(request, self._response), self.on_error])

    def on_error(self, res):
        try:
            res.get()
        except ChokeEvent:
            pass
        except StopIteration:
            pass
        except Exception as err:
            self._logger.error(repr(err), exc_info=True)
            traceback.print_stack()
            if not self._response.closed:
                self._response.error(1, "Error in event '%s' handler %s" %
                                     (self._response.event,
                                      str(err)))
        finally:
            if not self._response.closed:
                self._logger.info("Handler for %s didn't close response stream" % self._response.event)

    def close(self):
        self._state = None

# ===========================================


class _Function(_Proxy):
    """Wrapper for function object"""

    def __init__(self, func):
        self._state = None
        self._func = func

    def invoke(self, request, stream):
        self._state = 1
        self._response = stream
        self._request = request
        try:
            self._func(self._request, self._response)
        except Exception as err:
            self._logger.error("Caught exception in invoke(): %s" % str(err))
            traceback.print_stack()
            raise

    def push(self, chunk):
        try:
            self._func(chunk, self._response)
        except Exception as err:
            self._logger.error("Caught exception in push(): %s" % str(err))
            traceback.print_stack()
            raise

    def close(self):
        self._state = None

# =========================================


def type_traits(func_or_generator):
    """ Return class object depends on type of callable object """
    if compiler.consts.CO_GENERATOR & func_or_generator.func_code.co_flags:  # Coroutine
        return _Coroutine
    else:
        return _Function


def patch_response(obj, response_handler):
    def decorator(handler):
        def dec(func):
            def wrapper(request, response):
                return func(request, handler(response))
            return wrapper
        return dec

    obj.invoke = decorator(response_handler)(obj.invoke)
    return obj


def patch_request(obj, request_handler):
    def req_decorator(handler):
        def dec(func):
            def wrapper(request, response):
                return func(handler(request), response)
            return wrapper
        return dec

    obj.invoke = req_decorator(request_handler)(obj.invoke)
    return obj


def proxy_factory(func, request_handler=None, response_handler=None):
    def wrapper():
        _factory = type_traits(func)
        obj = _factory(func)
        if response_handler is not None:
            obj = patch_response(obj, response_handler)
        if request_handler is not None:
            obj = patch_request(obj, request_handler)
        return obj
    return wrapper
