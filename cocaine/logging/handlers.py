import logging

from cocaine.logging.logger import Logger

__author__ = 'Evgeny Safronov <division494@gmail.com>'


BLACK, RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE = range(8)
RESET_SEQ = "\033[0m"
COLOR_SEQ = "\033[1;%dm"
BOLD_SEQ = "\033[1m"


COLORS = {
    'DEBUG': WHITE,
    'INFO': GREEN,
    'WARNING': YELLOW,
    'CRITICAL': YELLOW,
    'ERROR': RED
}


class ColoredFormatter(logging.Formatter):
    def __init__(self, msg, colored=True):
        logging.Formatter.__init__(self, msg)
        self.colored = colored

    def format(self, record):
        levelname = record.levelname
        if self.colored and levelname in COLORS:
            record.msg = COLOR_SEQ % (30 + COLORS[levelname]) + str(record.msg) + RESET_SEQ
        return logging.Formatter.format(self, record)


def interactiveEmit(self, record):
    # Monkey patch Emit function to avoid new lines between records
    try:
        if str(record.msg).endswith('... '):
            fs = '%s'
        else:
            fs = '%s\n'
        msg = self.format(record)
        stream = self.stream
        if not hasattr(logging, '_unicode') or not logging._unicode:  # if no unicode support...
            stream.write(fs % msg)
        else:
            try:
                if isinstance(msg, unicode) and getattr(stream, 'encoding', None):
                    ufs = fs.decode(stream.encoding)
                    try:
                        stream.write(ufs % msg)
                    except UnicodeEncodeError:
                        stream.write((ufs % msg).encode(stream.encoding))
                else:
                    stream.write(fs % msg)
            except UnicodeError:
                stream.write(fs % msg.encode("UTF-8"))
        self.flush()
    except (KeyboardInterrupt, SystemExit):
        raise
    except:
        self.handleError(record)


class CocaineHandler(logging.Handler):
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
