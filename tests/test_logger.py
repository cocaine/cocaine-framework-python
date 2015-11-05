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
from tornado.test.util import unittest

from cocaine.logger import Logger
from cocaine.logger import CocaineHandler


def test_logger():
    ioloop = IOLoop.current()
    logger = Logger()
    assert logger is Logger()

    def main():
        logger.debug("debug_msg", extra={"A": 1, "B": 2.0})
        logger.info("info_msg", extra={"A": 1, "B": 2})
        logger.warning("warning_msg", extra={"A": 1, "B": 2.4})
        logger.error("error_msg", extra={"A": 1, "BoolFlag": False})
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


class LogFormatterTest(unittest.TestCase):
    def setUp(self):
        self.logger = Logger()

    def test_default_format_with_args(self):
        self.addCleanup(lambda: setattr(self.logger, "_defaultattrs", []))
        self.logger._defaultattrs = [("default1", "abc")]
        msg = self.logger.prepare_message_args(100, "format %s %d", "me", 200,
                                               extra={"A": 1, "B": True, 300: [1, 2]})
        self.assertEqual(msg, [100, self.logger.target,
                               "format me 200",
                               [("A", 1), ("B", True), ("300", "[1, 2]"), ('default1', 'abc')]])

    def test_bad_format_args(self):
        msg = self.logger.prepare_message_args(100, "format %s %d", "me")
        self.assertEqual(len(msg), 3)
        self.assertTrue(msg[2].startswith("unformatted:"))
