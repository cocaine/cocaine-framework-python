# encoding: utf-8

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
    elif isinstance(response, types.GeneratorType) or isinstance(response, Iterable):
        [pack(chunk, io) for chunk in response]
    elif response is not None:
        msgpack.pack(response, io)

def zeromq(function):
    @wraps(function)
    def wrapper(io):
        pack(function(msgpack.unpack(io)), io)

    return wrapper

def simple(function):
    @wraps(function)
    def wrapper(io):
        pack({'code': 200, 'headers': [('Content-type', 'text/plain')], io)
        pack(function(**msgpack.unpack(io)), io)

    return wrapper

def http(function):
    @wraps(function):
    def wrapper(io):
        code, headers, result = function(**msgpack.unpack(io))
        pack({'code': code, 'headers': headers})
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
            'REMOTE_PORT':          meta.get('remote_port', ''),,
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
        pack(result, io)

        if hasattr(result, 'close'):
            result.close()

    return wrapper
