#
#   Copyright (c) 2011-2013 Anton Tyurin <noxiouz@yandex.ru>
#    Copyright (c) 2011-2013 Other contributors as noted in the AUTHORS file.
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

from __future__ import print_function
import sys
import threading

from cocaine.asio.service import Service
from cocaine.logging.log_message import Message

__all__ = ["Logger"]


LOCK = threading.Lock()


VERBOSITY_LEVELS = {
    "ignore": 0,
    "error": 1,
    "warn": 2,
    "warning": 2,
    "info": 3,
    "debug": 4
}


class _STDERR_Logger(object):

    def debug(self, data):
        print(data, file=sys.stderr)

    def info(self, data):
        print(data, file=sys.stderr)

    def warn(self, data):
        print(data, file=sys.stderr)

    def warning(self, data):
        print(data, file=sys.stderr)

    def error(self, data):
        print(data, file=sys.stderr)

    def ignore(self, data):
        print(data, file=sys.stderr)


def _construct_logger_methods(cls, verbosity_level):
    def closure(_lvl):
        if _lvl <= verbosity_level:
            def func(data):
                with cls._lock:
                    cls._counter += 1
                    cls._logger._writableStream.write(Message("Message", cls._counter, _lvl, cls.target, "%s" % data).pack())
            return func
        else:
            def func(data):
                pass
            return func

    setattr(cls, "_counter", 0)
    for name, level in VERBOSITY_LEVELS.iteritems():
        setattr(cls, name, closure(level))


class _Logger(Service):
    def __init__(self):
        super(_Logger, self).__init__('logging')

    def _on_message(self, args):
        pass


class Logger(object):
    def __new__(cls):
        with LOCK:
            cls._lock = threading.Lock()
            if not hasattr(cls, "_instance"):
                instance = object.__new__(cls)
                try:
                    _logger = _Logger()
                    for verbosity in _logger.perform_sync("verbosity"):  # only one chunk and read choke also.
                        pass
                    setattr(instance, "_logger", _logger)
                    try:
                        setattr(instance, "target", "app/%s" % sys.argv[sys.argv.index("--app") + 1])
                    except ValueError:
                        setattr(instance, "target", "app/%s" % "standalone")
                    _construct_logger_methods(instance, verbosity)
                except Exception as err:
                    instance = _STDERR_Logger()
                    instance.warn("Logger init error: %s. Use stderr logger" % err)
                cls._instance = instance
        return cls._instance
