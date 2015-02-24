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

import functools

from .http import tornado_http

from tornado.wsgi import WSGIContainer


def start_response(func, status, response_headers, exc_info=None):
    if exc_info:
        try:
            raise (exc_info[0], exc_info[1], exc_info[2])
        finally:
            exc_info = None  # Avoid circular ref.

    return func.write_head(int(status.split(' ')[0]), response_headers)


def wsgi(application):
    @tornado_http
    def wrapper(request, response):
        req = yield request.read()
        for data in application(WSGIContainer.environ(req), functools.partial(start_response, response)):
            response.write(data)
        response.close()
    return wrapper
