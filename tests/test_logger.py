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

import logging
import time

from tornado.ioloop import IOLoop

from cocaine.logger import Logger
from cocaine.logger import CocaineHandler


def test_logger():
    ioloop = IOLoop.current()
    logger = Logger()
    assert logger is Logger()

    def main():
        logger.debug("debug_msg", extra={"A": 1, "B": 2})
        logger.info("info_msg", extra={"A": 1, "B": 2})
        logger.warning("warning_msg", extra={"A": 1, "B": 2})
        logger.error("error_msg", extra={"A": 1, "B": 2})
        logger.debug("debug_mesg")

        logger.info("message without attributes")
        logger.error("message with converted attributes", extra={1: "BAD_ATTR"})
        logger.error("message with bad extra", extra=("A", "B"))
        logger.error("message with bad extra", extra={"ATTR": [1, 2, 3]})
        logger.error("format %s %d", "str", 100, extra={"level": "error"})
        logger.info("badformat %s %d", "str", extra={"level": "error"})

        try:
            l = logging.getLogger("cocaine.testlogger")
            lh = CocaineHandler()
            l.setLevel(logging.DEBUG)
            l.addHandler(lh)
            l.info("logged via logging %s", "handler")
        finally:
            l.removeHandler(lh)

    ioloop.add_timeout(time.time() + 3, ioloop.stop)
    ioloop.add_callback(main)
    ioloop.start()
