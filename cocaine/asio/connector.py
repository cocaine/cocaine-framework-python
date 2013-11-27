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
import logging
import socket
import time

from tornado import stack_context
from tornado.ioloop import IOLoop

from ..concurrent import Deferred

from .exceptions import ResolveError, ConnectError, TimeoutError
from .stream import CocaineStream

__author__ = 'Evgeny Safronov <division494@gmail.com>'


log = logging.getLogger(__name__)


class _Timeout(object):
    def __init__(self, value):
        self.value = value
        self.id = 0


class ServiceConnector(object):
    def __init__(self, host, port, timeout=None, io_loop=None):
        self.host = host
        self.port = port
        self.timeout = _Timeout(timeout) if timeout is not None else None
        self.io_loop = io_loop or IOLoop.current()

        self.deferred = None

    def connect(self):
        if self.deferred is not None:
            return self.deferred

        log.debug('connecting to %s:%d', self.host, self.port)
        candidates = socket.getaddrinfo(self.host, self.port, 0, socket.SOCK_STREAM)
        if not candidates:
            log.warn('could not resolve %s:%d', self.host, self.port)
            raise ResolveError()

        log.debug('candidates: %s', candidates)

        self.deferred = Deferred()
        if self.timeout is not None:
            deadline = time.time() + self.timeout.value
            self.timeout.id = self.io_loop.add_timeout(deadline, self._handle_connection_timeout)

        df = self._try_connect(candidates[0])
        df.add_callback(stack_context.wrap(functools.partial(self._handle_connection, candidates=candidates[1:])))
        return self.deferred

    def _try_connect(self, candidate):
        family, socktype, proto, canonname, address = candidate
        log.debug(' - trying [%d] %s', proto, address)
        deferred = Deferred()
        try:
            sock = socket.socket(family=family, type=socktype, proto=proto)
            self._stream = CocaineStream(sock, io_loop=self.io_loop)
            self._stream.connect(address, callback=deferred.trigger)
            self._stream.set_close_callback(functools.partial(self._handle_connection_error, deferred))
        except Exception as err:
            log.warn(' - failed: %s', err)
            deferred.error(err)
        return deferred

    def _handle_connection(self, future, candidates):
        try:
            future.get()
        except Exception as err:
            log.warn(' - failed: %s', err)
            if candidates:
                df = self._try_connect(candidates[0])
                callback = stack_context.wrap(functools.partial(self._handle_connection, candidates=candidates[1:]))
                df.add_callback(callback)
            else:
                df = self.deferred
                self.deferred = None
                df.error(ConnectError())
        else:
            log.debug(' - success')
            if self.timeout is not None:
                self.io_loop.remove_timeout(self.timeout.id)
                self.timeout = None
            self._stream.set_close_callback(None)
            df = self.deferred
            self.deferred = None
            df.trigger(self._stream)

    def _handle_connection_error(self, deferred):
        deferred.error(ConnectError(self._stream.error))

    def _handle_connection_timeout(self):
        self.io_loop.remove_timeout(self.timeout.id)
        self.timeout = None
        self.deferred.error(TimeoutError())