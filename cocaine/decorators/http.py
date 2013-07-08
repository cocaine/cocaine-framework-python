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

import msgpack

from _callablewrappers import proxy_factory

__all__ = ["http"]


class _HTTPResponse(object):

    def __init__(self, stream):
        self._stream = stream

    def write(self, body):
        self._stream.write(body)

    def write_head(self, code, headers):
        self._stream.write({'code': code, 'headers' : headers})

    def close(self):
        self._stream.close()

    def error(self, *args, **kwargs):
        return self._stream.error(*args, **kwargs)

    @property
    def closed(self):
        return self._stream.closed


class _HTTPRequest(object):

    def __init__(self, data):
        self._data = msgpack.unpackb(data)

    @property
    def body(self):
        """Return request body"""
        return self._data['body']

    @property
    def meta(self):
        """ Return dict like:
        {'cookies': {},
        'headers': {'ACCEPT': '*/*',
        'CONTENT-TYPE': '',
        'HOST': 'somehost',
        'USER-AGENT': 'curl/7.19.7 (x86_64-pc-linux-gnu) libcurl/7.19.7 OpenSSL/0.9.8k zlib/1.2.3.3 libidn/1.15'},
        'host': 'someurl.com',
        'method': 'GET',
        'path_info': '',
        'query_string': 'partnerID=ntp_tb',
        'remote_addr': '1.11.111.111',
        'script_name': '/someone/get/',
        'secure': False,
        'server_addr': '1.1.1.1',
        'url': 'someurl'}
        """
        return self._data['meta']

    @property
    def request(self):
        return self._data['request']


def http_request_decorator(obj):
    def dec(func):
        def wrapper(chunk):
            return func(_HTTPRequest(chunk))
        return wrapper
    obj.push = dec(obj.push)
    return obj


def http(func):
    return proxy_factory(func, response_handler=_HTTPResponse, request_handler=http_request_decorator)
