from __future__ import print_function

import contextlib
import sys


__author__ = 'EvgenySafronov <division494@gmail.com>'


@contextlib.contextmanager
def printer(message, *args):
    status, reason, color = '', '', ''
    message = message % args
    try:
        _print(status, message, color, '\r')

        def write(msg):
            status = msg

        yield write
        status, reason, color = 'OK', '', Color.GREEN
    except Exception as err:
        status, reason, color = 'FAIL', err, Color.RED
        raise
    finally:
        _print(status, message, color, '\n')


def _print(status, message, color, suffix):
    status = '{:^6}'.format(status)
    formatted = '[{}{}{}] {}{}'.format(color, status, Color.RESET, message, suffix)
    sys.stdout.write(formatted)
    sys.stdout.flush()


class Color:
    RESET = '\033[0m'
    BLACK, RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE = ['\033[1;%dm' % (30 + id_) for id_ in range(8)]
