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
    import Cookie  # py2
except ImportError:  # pragma: no cover
    import http.cookies as Cookie  # py3

try:
    import urlparse
except ImportError:  # pragma: no cover
    from urllib import parse as urlparse

from tornado import gen
from tornado.escape import native_str
from tornado.httputil import (
    HTTPHeaders,
    HTTPServerRequest,
    parse_body_arguments)

from ..detail.util import msgpack_packb
from ..detail.util import msgpack_unpackb


__all__ = ["http", "tornado_http"]


def dict_list_to_single(inp):
    return dict((k, v[0]) for k, v in inp.items() if len(v) > 0)


def http_parse_cookies(headers):
    if 'Cookie' not in headers:
        return {}

    try:
        cookies = Cookie.SimpleCookie()
        cookies.load(native_str(headers["Cookie"]))
        return dict((key, name.value) for key, name in cookies.items())
    except Exception:
        return {}


class _HTTPRequest(object):
    def __init__(self, data):
        method, url, version, headers, self._body = msgpack_unpackb(data)
        self._headers = HTTPHeaders(headers)
        self._meta = {
            'method': method,
            'version': version,
            'host': self._headers.get('Host', ''),
            'remote_addr': self._headers.get('X-Real-IP') or self._headers.get('X-Forwarded-For', ''),
            'query_string': urlparse.urlparse(url).query,
            'cookies': dict(),
            'parsed_cookies': http_parse_cookies(self._headers),
        }
        args = urlparse.parse_qs(urlparse.urlparse(url).query)
        self._files = dict()
        parse_body_arguments(self._headers.get("Content-Type", ""), self._body, args, self._files)
        self._request = dict_list_to_single(args)

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


# Note: there's inconsistency between
# native-proxy and torando-proxy in version.
# version is sent by native as "1.1",
# but tornado sends "HTTP/1.1"
def format_http_version(version):
    if version.startswith("HTTP"):
        return version
    else:
        return "HTTP/%s" % version


def tornado_request_handler(data):
    unpacked_data = msgpack_unpackb(data)
    method, uri, version, headers, body = unpacked_data
    version = format_http_version(version)
    return HTTPServerRequest(method, uri, version, HTTPHeaders(headers), body)


class PatchedWebRequest(object):
    def __init__(self, request):
        self.request = request
        self.first = True

    @gen.coroutine
    def read(self):
        data = yield self.request.read()
        if self.first:
            self.first = False
            raise gen.Return(self.handle(data))
        raise gen.Return(data)

    def handle(self, data):
        raise NotImplementedError  # pragma: no cover


class HTTPPatchedRequest(PatchedWebRequest):
    def handle(self, data):
        return _HTTPRequest(data)


class TornadoPatchedRequest(PatchedWebRequest):
    def handle(self, data):
        return tornado_request_handler(data)


def tornado_http(func):
    func = gen.coroutine(func)

    def wrapper(request, response):
        yield func(TornadoPatchedRequest(request), _HTTPResponse(response))
    return wrapper


def http(func):
    func = gen.coroutine(func)

    def wrapper(request, response):
        yield func(HTTPPatchedRequest(request), _HTTPResponse(response))
    return wrapper
