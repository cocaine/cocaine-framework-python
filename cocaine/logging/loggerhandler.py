from __future__ import absolute_import

import logging

from cocaine.logging import Logger


class LoggerHandler(logging.Handler):
    def __init__(self):
        logging.Handler.__init__(self)
        self._logger = Logger()
        self.LEVEL_BINDS = {
            logging.DEBUG: self._logger.debug,
            logging.INFO: self._logger.info,
            logging.WARNING: self._logger.warn,
            logging.ERROR: self._logger.error
        }

    def emit(self, record):
        def dummy(*args):
            pass
        msg = self.format(record)
        self.LEVEL_BINDS.get(record.levelno, dummy)(msg)