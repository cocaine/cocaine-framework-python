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
import cStringIO

import msgpack

__all__ = ["ProxyCoroutine", "ProxyCollect", "ProxyFunc", "ProxyHTTP"]

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
    def invoke(self):
        pass

    @abstractmethod
    def close(self):
        pass


class ProxyCoroutine(_Proxy):
    """ Wrapper on coroutine-like function. Call next() for contained object on Invoke.\
        Then call send() method."""

    def __init__(self, generator, *args, **kwargs):
        self._response = None
        self._obj = generator
        self._func = None

    def __call__(self, *args):
        self._func.send(*args)

    def invoke(self):
        self._response = cStringIO.StringIO()
        self._func = self._obj(self._response)
        self._func.next()

    def close(self):
        self._func.throw(Exception("CHOKE"))
        ret = self._response.getvalue()
        try:
            self._response.close()
        except Exception:
            pass
        return ret


class ProxyFunc(_Proxy):
    """ Wrapper on simply fucntion """

    def __init__(self, func):
        self._response = None
        self._request = None
        self._obj = func

    def __call__(self, chunk=None):
        pass

    def invoke(self):
        self._response = cStringIO.StringIO()
        self._request = cStringIO.StringIO()
        self._obj(self._response)
        #print self._response.getvalue()

    def close(self):
        self._response.close()
        self._request.close()


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


#
# #####################################################
#

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
        self._func.send(chunk)

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
        #self._func.throw(Exception("CHOKE"))
        self._state = None

    @property
    def closed(self):
        return self._state is None
