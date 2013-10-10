from __future__ import print_function

import contextlib
import sys

from cocaine.tools import log


__author__ = 'EvgenySafronov <division494@gmail.com>'


ENABLE_OUTPUT = False


class Color:
    RESET = '\033[0m'
    OFFSET = 30
    BLACK, RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE = ['\033[1;%dm' % (OFFSET + id_) for id_ in range(8)]


class Result(object):
    def __init__(self):
        self.value = ''

    def set(self, msg, *args):
        self.value = ' - {0}'.format('{0}{1}{2}'.format(Color.WHITE, msg % args, Color.RESET))

    def __str__(self):
        return str(self.value)


def _print(status, message, color, suffix):
    status = '{:^6}'.format(status)
    formatted = '[{0}{1}{2}] {3}{4}'.format(color, status, Color.RESET, message, suffix)
    if ENABLE_OUTPUT:
        sys.stdout.write(formatted)
        sys.stdout.flush()
    else:
        log.debug(formatted)


def print_start(message):
    _print('', message, Color.WHITE, '\r')


def print_success(message):
    _print('OK', message, Color.GREEN, '\n')


def print_error(message):
    _print('FAIL', message, Color.RED, '\n')


@contextlib.contextmanager
def printer(message, *args):
    result = Result()
    message = message % args

    try:
        print_start(message)
        yield result.set
        print_success('{0}{1}'.format(message, result))
    except Exception:
        print_error('{0}{1}'.format(message, result))
        raise
