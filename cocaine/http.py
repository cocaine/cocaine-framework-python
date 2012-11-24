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

from cocaine import emitter
from functools import wraps

import msgpack

__all__ = ["http"]

class HTTPReadableStream(emitter.EventSource):
    def __init__(self, request):
        super(HTTPReadableStream, self).__init__()

        request.on("chunk", self.process)
        request.on("close", self.close)

        self.headers = {}

    def process(self, chunk):
        if not self.headers:
            self.headers = msgpack.unpackb(chunk)
            self.invoke("request")
            return
            
        self.invoke("body", chunk)

    def close(self):
        self.invoke("close")

class HTTPWritableStream(object):
    def __init__(self, response):
        self.response = response

    def writeHead(self, code, headers):
        head = msgpack.packb({
            'code': code,
            'headers': headers.items()
        })

        self.response.write(head)

    def write(self, body):
        self.response.write(body)

    def close(self):
        self.response.close()

def http(function):
    @wraps(function)
    def wrapper(request, response):
        request = HTTPReadableStream(request)
        response = HTTPWritableStream(response)

        function(request, response)

    return wrapper
