#
#    Copyright (c) 2014+ Anton Tyurin <noxiouz@yandex.ru>
#    Copyright (c) 2014+ Evgeny Safronov <division494@gmail.com>
#    Copyright (c) 2011-2014 Other contributors as noted in the AUTHORS file.
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


from tornado import gen

from ..common import CocaineErrno

__all__ = ["proxy_factory"]


class _Context(object):
    """Wrapper for coroutine function """
    _wrapped = True

    def __init__(self, func):
        self._obj = func

    def invoke(self, request, response, loop):
        def trap(res):
            try:
                res.result()
                if not response.closed:
                    response.close()
            except Exception as err:
                response.error(CocaineErrno.EUNCAUGHTEXCEPTION, str(err))
        loop.add_future(self._obj(request, response), trap)


def patch_response(obj, response_handler):
    def decorator(handler):
        def dec(func):
            def wrapper(request, response, loop):
                return func(request, handler(response), loop)
            return wrapper
        return dec

    obj.invoke = decorator(response_handler)(obj.invoke)
    return obj


def patch_request(obj, request_handler):
    def req_decorator(handler):
        def dec(func):
            def wrapper(request, response, loop):
                return func(handler(request), response, loop)
            return wrapper
        return dec

    obj.invoke = req_decorator(request_handler)(obj.invoke)
    return obj


def proxy_factory(func, request_handler=None, response_handler=None):
    func = gen.coroutine(func)

    def wrapper():
        obj = _Context(func)
        if response_handler is not None:
            obj = patch_response(obj, response_handler)
        if request_handler is not None:
            obj = patch_request(obj, request_handler)
        return obj
    return wrapper


def default(func):
    return proxy_factory(func, request_handler=None, response_handler=None)
