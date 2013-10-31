import contextlib
import functools

from ..concurrent import Deferred

__author__ = 'Evgeny Safronov <division494@gmail.com>'


@contextlib.contextmanager
def trigger_check(self):
    class Trigger(object):
        def __init__(self):
            self.flag = False

        def toggle(self):
            self.flag = True

        def __nonzero__(self):
            return self.flag

    trigger = Trigger()
    try:
        yield trigger
    finally:
        self.assertTrue(trigger, 'trigger is not triggered')


class DeferredMock(Deferred):
    def __init__(self, pending, io_loop):
        super(DeferredMock, self).__init__()
        for value in pending:
            func = self.error if isinstance(value, Exception) else self.trigger
            io_loop.add_callback(functools.partial(func, value))
