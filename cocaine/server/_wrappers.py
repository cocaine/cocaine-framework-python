#
#    Copyright (c) 2013+ Evgeny Safronov <division494@gmail.com>
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

__author__ = 'Evgeny Safronov <division494@gmail.com>'


import abc
import functools
import inspect
import traceback

from .. import concurrent
from ..protocol import ChokeEvent
from ..server._log import log


__all__ = ["proxy_factory"]


class _Proxy(object):
    __metaclass__ = abc.ABCMeta
    _wrapped = True

    @abc.abstractmethod
    def invoke(self, request, response):
        pass


class _Coroutine(_Proxy):
    def __init__(self, func):
        self._func = func

    def invoke(self, request, response):
        deferred = concurrent.engine(self._func)(request, response)
        deferred.add_callback(functools.partial(self._finally, response))

    def _finally(self, response, result):
        try:
            result.get()
        except (StopIteration, ChokeEvent):
            pass
        except Exception as err:
            log.error(repr(err), exc_info=True)
            if not response.closed:
                response.error(1, 'error handler %s', err)
        finally:
            if not response.closed:
                log.info('handler did not close response stream')


class _Function(_Proxy):
    def __init__(self, func):
        self._func = func

    def invoke(self, request, response):
        try:
            self._func(request, response)
        except Exception as err:
            log.error('Caught exception in invoke(): %s', err)
            traceback.print_stack()
            raise


def type_traits(func):
    if inspect.isgeneratorfunction(func):
        return _Coroutine
    else:
        return _Function


def patch_response(invokable, response_handler):
    def decorator(handler):
        def dec(func):
            def wrapper(request, response):
                return func(request, handler(response))
            return wrapper
        return dec

    invokable.invoke = decorator(response_handler)(invokable.invoke)
    return invokable


def patch_request(invokable, request_handler):
    def decorator(handler):
        def dec(func):
            def wrapper(request, response):
                return func(handler(request), response)
            return wrapper
        return dec

    invokable.invoke = decorator(request_handler)(invokable.invoke)
    return invokable


def proxy_factory(func, request_handler=None, response_handler=None):
    def wrapper():
        _factory = type_traits(func)
        invokable = _factory(func)
        if response_handler is not None:
            invokable = patch_response(invokable, response_handler)
        if request_handler is not None:
            invokable = patch_request(invokable, request_handler)
        return invokable
    return wrapper


def default(func):
    return proxy_factory(func, None, None)