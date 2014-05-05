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
import logging

# from ._wrappers import default

log = logging.getLogger("asyncio")
log.setLevel(logging.INFO)


def default(f):
    print "DEFAULT"


class Sandbox(object):
    def __init__(self):
        self._events = {}

    def on(self, event, function):
        try:
            closure = function()
        except Exception:
            closure = default(function)()
            if hasattr(closure, '_wrapped'):
                function = default(function)
        else:
            if not hasattr(closure, '_wrapped'):
                function = default(function)
        self._events[event] = function

    def invoke(self, event, request, response):
        log.debug('invoking "%s" event', event)
        try:
            handler = self._events[event]
        except KeyError:
            log.warn('there is no handler for event %s', event)
            response.error(-100, 'there is no handler for event %s', event)
        else:
            handler().invoke(request, response)
