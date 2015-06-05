#
#    Copyright (c) 2011-2012 Andrey Sibiryov <me@kobology.ru>
#    Copyright (c) 2012+ Anton Tyurin <noxiouz@yandex.ru>
#    Copyright (c) 2013+ Evgeny Safronov <division494@gmail.com>
#    Copyright (c) 2011-2014 Other contributors as noted in the AUTHORS file.
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

try:
    import urlparse
    import Cookie as cookies
except ImportError:  # pragma: no cover
    from urllib import parse as urlparse
    from http import cookies

from tornado import escape
from tornado.httputil import (
    HTTPHeaders,
    HTTPServerRequest,
    parse_body_arguments)

from ..detail.util import msgpack_packb
from ..detail.util import msgpack_unpackb
from ..worker._wrappers import proxy_factory


__all__ = ["http", "tornado_http"]


class _HTTPRequest(object):
    def __init__(self, data):
        unpacked_data = msgpack_unpackb(data)
        method, url, version, headers, self._body = unpacked_data
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
                parsed_cookies = cookies.BaseCookie()
                parsed_cookies.load(escape.native_str(self._headers['Cookie']))
                self._meta['parsed_cookies'] = dict((key, name.value) for key, name in parsed_cookies.items())
            except Exception:
                pass

        tmp = urlparse.parse_qs(urlparse.urlparse(url).query)
        self._request = dict((k, v[0]) for k, v in tmp.items() if len(v) > 0)
        self._files = None
        args, files = dict(), dict()
        parse_body_arguments(self._headers.get("Content-Type", ""), self._body, args, files)
        self._request.update(dict((k, v[0]) for k, v in args.items() if len(v) > 0))
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


class _HTTPResponse(object):
    def __init__(self, stream):
        self._stream = stream
        self.event = self._stream.event

    def write(self, body):
        self._stream.write(body)

    def write_head(self, code, headers):
        if isinstance(headers, dict):
            headers = headers.items()
        self._stream.write(msgpack_packb((code, headers)))

    def close(self):
        self._stream.close()

    def error(self, *args, **kwargs):
        return self._stream.error(*args, **kwargs)

    @property
    def closed(self):
        return self._stream.closed


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
# but tornado sends "HTTP/1.1"
def format_http_version(version):
    if version.startswith("HTTP"):
        return version
    else:
        return "HTTP/%s" % version


def _tornado_request_wrapper(data):
    unpacked_data = msgpack_unpackb(data)
    method, uri, version, headers, body = unpacked_data
    version = format_http_version(version)
    return HTTPServerRequest(method, uri, version, HTTPHeaders(headers), body)


def tornado_request_decorator(obj):
    def dec(func):
        def wrapper(chunk):
            return func(_tornado_request_wrapper(chunk))
        return wrapper
    obj.push = dec(obj.push)
    return obj


def tornado_http(func):
    return proxy_factory(func,
                         response_handler=_HTTPResponse,
                         request_handler=tornado_request_decorator)


def http(func):
    return proxy_factory(func,
                         response_handler=_HTTPResponse,
                         request_handler=http_request_decorator)
