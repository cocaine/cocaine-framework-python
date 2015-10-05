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

import functools
import logging
import threading

from .api import API
from .defaults import Defaults
from .defaults import GetOptError
from .service import Service


LOCATOR_DEFAULT_ENDPOINT = Defaults.locators


VERBOSITY_LEVELS = {
    "debug": 0,
    "info": 1,
    "warn": 2,
    "warning": 2,
    "error": 3,
}


def thread_once(class_init):
    @functools.wraps(class_init)
    def wrapper(self, *args, **kwargs):
        if getattr(self._current, "initialized", False):
            return

        class_init(self, *args, **kwargs)

        self._current.initialized = True
    return wrapper


def on_emit_constructor(self, level, uuid):
    target = self._target

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


# ToDo:
# * Add fallback implementation
# * Loglevels mapping
class Logger(Service):
    _current = threading.local()

    def __new__(cls, *args, **kwargs):
        if not getattr(cls._current, "instance", None):
            cls._current.instance = object.__new__(cls, *args, **kwargs)
        return cls._current.instance

    @thread_once
    def __init__(self, endpoints=LOCATOR_DEFAULT_ENDPOINT, io_loop=None):
        super(Logger, self).__init__(name="logging",
                                     endpoints=endpoints,
                                     io_loop=io_loop)
        self.api = API.Logger
        self._target = Defaults.app

        try:
            _uuid = Defaults.uuid
        except GetOptError:
            _uuid = None

        for level_name, level in VERBOSITY_LEVELS.items():
            setattr(self, level_name, on_emit_constructor(self, level, _uuid))


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
