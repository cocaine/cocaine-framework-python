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

from __future__ import print_function

import sys
import threading

from .service import Service
from .api import API


LOCK = threading.Lock()


VERBOSITY_LEVELS = {
    "debug": 0,
    "info": 1,
    "warn": 2,
    "warning": 2,
    "error": 3,
}


class _Logger(Service):
    def __init__(self, host="localhost", port=10053, loop=None):
        super(_Logger, self).__init__(name="logging",
                                      host=host, port=port, loop=loop)
        self.api = API.Logger
        try:
            setattr(self, "target", "app/%s" % sys.argv[sys.argv.index("--app") + 1])
        except ValueError:
            setattr(self, "target", "app/%s" % "standalone")

        def wrapper(level):
            target = self.target

            def on_emit(message, attrs):
                return self.emit(level, target, message, attrs)
            return on_emit

        for level_name, level in VERBOSITY_LEVELS.items():
            setattr(self, level_name, wrapper(level))


# class Logger(object):
#     def __new__(cls):
#         with LOCK:
#             cls._lock = threading.Lock()
#             if not hasattr(cls, "_instance"):
#                 instance = object.__new__(cls)
#                 try:
#                     _logger = Service("logging")
#                     verbosity = _logger.verbosity().wait()
#                     print(_logger.api)
#                     setattr(instance, "_logger", _logger)
#                     try:
#                         setattr(instance, "target", "app/%s" % sys.argv[sys.argv.index("--app") + 1])
#                     except ValueError:
#                         setattr(instance, "target", "app/%s" % "standalone")
#                     _construct_logger_methods(instance, verbosity)
#                 except Exception as err:
#                     instance = _STDERR_Logger()
#                     instance.warn("Logger init error: %s. Use stderr logger" % err)
#                 cls._instance = instance
#         return cls._instance
