#
#    Copyright (c) 2013+ Evgeny Safronov <division494@gmail.com>
#    Copyright (c) 2011-2013 Other contributors as noted in the AUTHORS file.
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

import functools

from greenlet import greenlet
from tornado.ioloop import IOLoop

from ..protocol import ChokeEvent
from . import service
from .base import LOCATOR_DEFAULT_HOST, LOCATOR_DEFAULT_PORT, log

__author__ = 'Evgeny Safronov <division494@gmail.com>'


def synchrony(func):
    def wrapper(*args, **kwargs):
        def run():
            fiber = greenlet(func)
            try:
                fiber.switch(*args, **kwargs)
            except Exception as err:
                log.warn('exception occurred: %s', err, exc_info=True)
        io_loop = IOLoop.current()
        io_loop.add_callback(run)
        io_loop.start()
    return wrapper


def _single_shot_handler(fiber, results, result):
    try:
        fiber.switch(result.get())
    except Exception as err:
        fiber.throw(err)


def _chunked_handler(fiber, results, result):
    try:
        results.append(result.get())
    except ChokeEvent:
        count = len(results)
        if count == 0:
            fiber.switch()
        elif count == 1:
            fiber.switch(results[0])
        else:
            fiber.switch(results)
    except Exception as err:
        fiber.throw(err)


def _make_sync(func, handler):
    def wrapper(*args, **kwargs):
        results = []
        fiber = greenlet.getcurrent()
        df = func(*args, **kwargs)
        df.add_callback(functools.partial(handler, fiber, results))
        return fiber.parent.switch()
    return wrapper


def sync(func):
    return _make_sync(func, _single_shot_handler)


def sync_chunked(func):
    return _make_sync(func, _chunked_handler)


DEFAULT_LOCATOR_ENDPOINT = (LOCATOR_DEFAULT_HOST, LOCATOR_DEFAULT_PORT)


class Service(object):
    def __init__(self, name, locator_endpoint=DEFAULT_LOCATOR_ENDPOINT):
        self.service = service.Service(name, blockingConnect=False)
        self._connect(*locator_endpoint)

    def _connect(self, host, port):
        sync(self.service.connect)(host, port)

        for state in self.service.states.values():
            if len(state.substates) == 0:
                setattr(self, state.name, sync_chunked(getattr(self.service, state.name)))
            else:
                setattr(self, state.name, getattr(self.service, state.name))
