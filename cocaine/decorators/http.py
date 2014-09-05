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

import urlparse
import Cookie

import msgpack

import tornado
from tornado.httputil import parse_body_arguments, HTTPHeaders
from tornado.httpserver import HTTPRequest

from _callablewrappers import proxy_factory


__all__ = ["http", "tornado"]


class _HTTPResponse(object):

    def __init__(self, stream):
        self._stream = stream
        self.event = self._stream.event

    def write(self, body):
        self._stream.write(body)

    def write_head(self, code, headers):
        self._stream.write((code, headers))

    def close(self):
        self._stream.close()

    def error(self, *args, **kwargs):
        return self._stream.error(*args, **kwargs)

    @property
    def closed(self):
        return self._stream.closed


class _HTTPRequest(object):

    def __init__(self, data):
        method, url, version, headers, self._body = msgpack.unpackb(data)
        self._meta = dict()
        self._headers = dict(headers)
        self._meta['method'] = method
        self._meta['version'] = version
        self._meta['host'] = self._headers.get('Host') or self._headers.get('host', '')
        self._meta['remote_addr'] = self._headers.get('X-Real-IP') or self._headers.get('X-Forwarded-For', '')
        self._meta['query_string'] = urlparse.urlparse(url).query
        self._meta['cookies'] = dict()
        if 'Cookie' in self._headers:
            try:
                cookies = Cookie.BaseCookie()
                cookies.load(tornado.escape.native_str(self._headers['Cookie']))
                self._meta['cookies'] = dict((key, name.value) for key, name in cookies.iteritems())
            except:
                pass

        tmp = urlparse.parse_qs(urlparse.urlparse(url).query)
        self._request = dict((k, v[0]) for k, v in tmp.iteritems() if len(v) > 0)
        self._files = None
        args = dict()
        files = dict()
        parse_body_arguments(self._headers.get("Content-Type", ""), self._body, args, files)
        self._request.update(dict((k, v[0]) for k, v in args.iteritems() if len(v) > 0))
        self._files = files

    @property
    def headers(self):
        return self._headers

    @property
    def body(self):
        """Return request body"""
        return self._body

    @property
    def meta(self):
        return self._meta

    @property
    def request(self):
        return self._request

    @property
    def files(self):
        return self._files


def http_request_decorator(obj):
    def dec(func):
        def wrapper(chunk):
            return func(_HTTPRequest(chunk))
        return wrapper
    obj.push = dec(obj.push)
    return obj


# Note: there's inconsistency between
# native-proxy and torando-proxy in version.
# version is sent by native as "1.1",
# but tornado sends version as "HTTP/1.1"
def format_http_version(version):
    if version.startswith("HTTP"):
        return version
    else:
        return "HTTP/%s" % version


if tornado.version_info[0] >= 4:
    # until 4.0.2 we need this workaround
    # to avoid AttributeError in constructor of HTTPServerRequest
    class _FakeConnection():
        def __init__(self):
            self.remote_ip = None
            self.context = self

    _fake_connection = _FakeConnection()

    def _tornado_request_wrapper(data):
        method, uri, version, headers, body = msgpack.unpackb(data)
        version = format_http_version(version)
        return HTTPRequest(method=method, uri=uri, version=version,
                           headers=HTTPHeaders(headers), body=body,
                           connection=_fake_connection)
else:
    def _tornado_request_wrapper(data):
        method, uri, version, headers, body = msgpack.unpackb(data)
        version = format_http_version(version)
        return HTTPRequest(method, uri, version, HTTPHeaders(headers), body)


def tornado_request_decorator(obj):
    def dec(func):
        def wrapper(chunk):
            return func(_tornado_request_wrapper(chunk))
        return wrapper
    obj.push = dec(obj.push)
    return obj


def http(func):
    return proxy_factory(func, response_handler=_HTTPResponse, request_handler=http_request_decorator)


def tornado(func):
    return proxy_factory(func, response_handler=_HTTPResponse, request_handler=tornado_request_decorator)
