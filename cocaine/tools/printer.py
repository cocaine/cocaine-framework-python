from __future__ import print_function

import contextlib
import sys


__author__ = 'EvgenySafronov <division494@gmail.com>'


@contextlib.contextmanager
def printer(message, *args):
    def _print(status, message, color, suffix):
        status = '{:^6}'.format(status)
        formatted = '[{0}{1}{2}] {3}{4}'.format(color, status, Color.RESET, message, suffix)
        sys.stdout.write(formatted)
        sys.stdout.flush()

    def print_start(message):
        _print('', message, Color.WHITE, '\r')

    def print_success(message):
        _print('OK', message, Color.GREEN, '\n')

    def print_error(message):
        _print('FAIL', message, Color.RED, '\n')

    class Result(object):
        def __init__(self):
            self.value = ''

        def set(self, msg, *args):
            self.value = ' - {0}'.format('{0}{1}{2}'.format(Color.WHITE, msg % args, Color.RESET))

        def __str__(self):
            return str(self.value)

    result = Result()
    message = message % args

    try:
        print_start(message)
        yield result.set
        print_success('{0}{1}'.format(message, result))
    except Exception:
        print_error('{0}{1}'.format(message, result))
        raise


class Color:
    RESET = '\033[0m'
    BLACK, RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE = ['\033[1;%dm' % (30 + id_) for id_ in range(8)]
