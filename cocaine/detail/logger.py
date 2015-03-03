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
import sys
import threading

from .service import Service
from .api import API


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


# ToDo:
# * Possiblly it's better to cache instances according to *args, **kwargs
# * Add fallback implementation
# * Loglevels mapping
class Logger(Service):
    _current = threading.local()

    def __new__(cls, *args, **kwargs):
        if not getattr(cls._current, "instance", None):
            cls._current.instance = object.__new__(cls, *args, **kwargs)
        return cls._current.instance

    @thread_once
    def __init__(self, host="localhost", port=10053, loop=None):
        super(Logger, self).__init__(name="logging",
                                     host=host, port=port, loop=loop)
        self.api = API.Logger
        try:
            setattr(self, "target", "app/%s" % sys.argv[sys.argv.index("--app") + 1])
        except ValueError:
            setattr(self, "target", "app/%s" % "standalone")

        def wrapper(level):
            target = self.target

            def on_emit(message, attrs=None):
                if attrs is None:
                    return self.emit(level, target, message)
                else:
                    return self.emit(level, target, message, attrs)
            return on_emit

        for level_name, level in VERBOSITY_LEVELS.items():
            setattr(self, level_name, wrapper(level))


class CocaineHandler(logging.Handler):
    def __init__(self, *args, **kwargs):
        super(CocaineHandler, self).__init__()

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
