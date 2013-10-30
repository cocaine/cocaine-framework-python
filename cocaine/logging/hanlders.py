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

from ..services.logger import Logger


__author__ = 'Evgeny Safronov <division494@gmail.com>'


VERBOSITY_LEVELS = {
    0: 'ignore',
    1: 'error',
    2: 'warn',
    3: 'info',
    4: 'debug',
}

VERBOSITY_MAP = {
    logging.DEBUG: 4,
    logging.INFO: 3,
    logging.WARN: 2,
    logging.ERROR: 1,
}


class CocaineHandler(logging.Handler):
    def __init__(self):
        logging.Handler.__init__(self)
        self._log = Logger.instance()
        self._dispatch = {}
        for level in VERBOSITY_LEVELS:
            self._dispatch[level] = functools.partial(self._log.emit, level)
        self.devnull = lambda msg: None

    def emit(self, record):
        msg = self.format(record)
        level = VERBOSITY_MAP.get(record.levelno, 0)
        self._dispatch.get(level, self.devnull)(msg)