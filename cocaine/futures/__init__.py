from time import time
from tornado import ioloop

class Sleep(object):
    """ Allow to attach callback,\
    which will be executed after giving period (in fact, not early).
    """

    def __init__(self, timeout):
        self._timeout = timeout

    def bind(self, callback, errorback=None, on_done=None):
        clbk = callback or on_done or errorback
        ioloop.IOLoop.instance().add_timeout(self._timeout+time(), clbk)

class NextTick(object):
    """ Allow to attach callback,\
    which will be executed on the next iteration of reactor loop.
    It's usefull for hard operations, using that from handle to avoid
    event loop blocking.
    """

    def __init__(self):
        pass

    def bind(self, callback, errorback=None, on_done=None):
        clbk = callback or on_done or errorback
        ioloop.IOLoop.instance().add_callback(clbk)
