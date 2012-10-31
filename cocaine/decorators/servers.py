# encoding: utf-8
#
#    Copyright (c) 2011-2012 Andrey Sibiryov <me@kobology.ru>
#    Copyright (c) 2011-2012 Other contributors as noted in the AUTHORS file.
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

import types
import msgpack
import os
import sys
from functools import wraps
from collections import Iterable

from cocaine.context import Log

__all__ = ["zeromq", "simple", "http", "wsgi"]

log = Log()

def pack(response, io):
    if isinstance(response, types.StringTypes):
        io.write(response)
    elif isinstance(response, dict):
        msgpack.pack(response, io)
    elif isinstance(response, types.GeneratorType):
        [pack(chunk, io) for chunk in response]
    elif response is not None:
        msgpack.pack(response, io)

def zeromq(function):
    @wraps(function)
    def wrapper(io):
        args = msgpack.unpack(io)

        if args is not None:
            result = function(args)
        else:
            result = function()

        pack(result, io)

    return wrapper

def simple(function):
    @wraps(function)
    def wrapper(io):
        result = function(**msgpack.unpack(io))
        pack({'code': 200, 'headers': [('Content-type', 'text/plain')]}, io)
        pack(result, io)

    return wrapper

def http(function):
    @wraps(function)
    def wrapper(io):
        code, headers, result = function(**msgpack.unpack(io))
        pack({'code': code, 'headers': headers}, io)
        pack(result, io)

    return wrapper

def wsgi(function):
    @wraps(function)
    def wrapper(io):
        http_dict = msgpack.unpack(io)
        meta = http_dict['meta']
        headers = meta['headers']
        cookies = meta['cookies']
        request = http_dict['request']

        environ = {
            'wsgi.version':         (1, 0),
            'wsgi.url_scheme':      'https' if meta['secure'] else 'http',
            'wsgi.input':           io,
            'wsgi.errors':          Log(),
            'wsgi.multithread':     False,
            'wsgi.multiprocess':    True,
            'wsgi.run_once':        False,
            'SERVER_SOFTWARE':      "Cocaine",
            'REQUEST_METHOD':       meta['method'],
            'SCRIPT_NAME':          meta.get('script_name', ''),
            'PATH_INFO':            meta.get('path_info', ''),
            'QUERY_STRING':         meta.get('query_string', ''),
            'CONTENT_TYPE':         headers.get('CONTENT-TYPE', ''),
            'CONTENT_LENGTH':       headers.get('CONTENT_LENGTH', ''),
            'REMOTE_ADDR':          meta.get('remote_addr', ''),
            'REMOTE_PORT':          meta.get('remote_port', ''),
            'SERVER_NAME':          '',
            'SERVER_PORT':          '',
            'SERVER_PROTOCOL':      '',
            'HTTP_HOST':            meta['host']
        }

        for key, value in headers.items():
            key = 'HTTP_' + key.upper().replace('-', '_')
            if key not in ('HTTP_CONTENT_TYPE', 'HTTP_CONTENT_LENGTH'):
                environ[key] = value

        def start_response(status, response_headers, exc_info=None):
            if exc_info:
                 try:
                     raise exc_info[0], exc_info[1], exc_info[2]
                 finally:
                     exc_info = None    # Avoid circular ref.

            pack({'code': int(status.split(' ')[0]), 'headers': response_headers}, io)

        result = function(environ, start_response)

        if (isinstance(response, Iterable)):
            [pack(chunk, io) for chunk in response]
        else:
           pack(result, io)

        if hasattr(result, 'close'):
            result.close()

    return wrapper
