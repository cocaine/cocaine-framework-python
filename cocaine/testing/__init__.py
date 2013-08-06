import functools

from cocaine.futures.chain import Chain

__author__ = 'Evgeny Safronov <division494@gmail.com>'


def gen_test(func):
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        Chain([lambda: func(self, *args, **kwargs), lambda result: self.ioLoop.stop()])
        self.ioLoop.start()
    return wrapper