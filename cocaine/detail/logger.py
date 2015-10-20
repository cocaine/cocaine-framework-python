#
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

import itertools
import functools
import logging
import threading

from tornado import gen

from tornado.gen import coroutine
from tornado.ioloop import IOLoop
from tornado.locks import Lock
from tornado.tcpclient import TCPClient

from .api import API
from .defaults import Defaults
from .defaults import GetOptError
from .util import msgpack_packb, msgpack_unpacker


__all__ = ["Logger", "CocaineHandler"]


LOCATOR_DEFAULT_ENDPOINTS = Defaults.locators


VERBOSITY_LEVELS = {
    "debug": 0,
    "info": 1,
    "warn": 2,
    "warning": 2,
    "error": 3,
}


# look at Locator and LoggerAPI
EMIT = 0
RESOLVE = 0
VALUE_CODE = 0
ERROR_CODE = 1
assert API.Logger[EMIT][0] == "emit"
assert API.Locator[RESOLVE][0] == "resolve"


def thread_once(class_init):
    @functools.wraps(class_init)
    def wrapper(self, *args, **kwargs):
        if getattr(self._current, "initialized", False):
            return

        class_init(self, *args, **kwargs)
        self._current.initialized = True
    return wrapper


def on_emit_constructor(self, level, uuid):
    target = self.target
    if uuid is None:
        def on_emit(message, attrs=None):
            if not isinstance(attrs, dict):
                return self.emit(level, target, message)
            else:
                return self.emit(level, target, message, attrs.items())
    else:
        def on_emit(message, attrs=None):
            if not isinstance(attrs, dict):
                return self.emit(level, target, message, [["uuid", uuid]])
            else:
                # ToDo: implement safe replace?
                attrs["uuid"] = uuid
                return self.emit(level, target, message, attrs.items())
    return on_emit


class Logger(object):
    _name = "logging"
    _current = threading.local()

    def __new__(cls, *args, **kwargs):
        if not getattr(cls._current, "instance", None):
            cls._current.instance = object.__new__(cls, *args, **kwargs)
        return cls._current.instance

    @thread_once
    def __init__(self, endpoints=LOCATOR_DEFAULT_ENDPOINTS, io_loop=None):
        self.io_loop = io_loop or IOLoop.current()
        self.endpoints = endpoints
        self._lock = Lock()

        self.counter = itertools.count(1)

        self.pipe = None
        self.target = Defaults.app

        try:
            _uuid = Defaults.uuid
        except GetOptError:
            _uuid = None

        for level_name, level in VERBOSITY_LEVELS.items():
            setattr(self, level_name, on_emit_constructor(self, level, _uuid))

    @coroutine
    def emit(self, *args):
        if not self._connected:
            yield self.connect()

        counter = next(self.counter)
        self.pipe.write(msgpack_packb([counter, EMIT, args]))


    @coroutine
    def connect(self):
        with (yield self._lock.acquire()):
            if self._connected:
                return

            for host, port in (yield resolve_logging(self.endpoints, self._name, self.io_loop)):
                try:
                    self.pipe = yield TCPClient(io_loop=self.io_loop).connect(host, port)
                    self.pipe.set_nodelay(True)
                    return
                except IOError:
                    pass

    @property
    def _connected(self):
        return self.pipe is not None and not self.pipe.closed()

    def disconnect(self):
        if self.pipe is None:
            return

        self.pipe.close()
        self.pipe = None

    def __del__(self):
        # we have to close owned connection
        # otherwise it would be a fd-leak
        self.disconnect()


@coroutine
def resolve_logging(endpoints, name="logging", io_loop=None):
    io_loop = io_loop or IOLoop.current()

    for host, port in endpoints:
        buff = msgpack_unpacker()
        locator_pipe = None
        try:
            locator_pipe = yield TCPClient(io_loop=io_loop).connect(host, port)
            locator_pipe.set_nodelay(True)
            request = msgpack_packb([999999, RESOLVE, [name]])
            yield locator_pipe.write(request)
            while True:
                data = yield locator_pipe.read_bytes(1024, partial=True)
                buff.feed(data)
                for msg in buff:
                    _, code, payload = msg[:3]
                    if code == VALUE_CODE:
                        raise gen.Return(payload[0])
        except (IOError, ValueError):
            pass
        finally:
            if locator_pipe:
                locator_pipe.close()

    raise Exception("unable to resolve logging")



class CocaineHandler(logging.Handler):
    def __init__(self, *args, **kwargs):
        logging.Handler.__init__(self)

        self._logger = Logger(*args, **kwargs)
        self.level_binds = {
            logging.DEBUG: self._logger.debug,
            logging.INFO: self._logger.info,
            logging.WARNING: self._logger.warn,
            logging.ERROR: self._logger.error
        }

    def emit(self, record):
        def dummy(*args):  # pragma: no cover
            pass
        msg = self.format(record)
        self.level_binds.get(record.levelno, dummy)(msg)
