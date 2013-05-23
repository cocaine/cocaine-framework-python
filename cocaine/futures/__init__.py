from time import time
from tornado import ioloop

class Sleep(object):

    def __init__(self, timeout):
        self._timeout = timeout

    def bind(self, callback, errorback=None, on_done=None):
        clbk = callback or on_done or errorback
        ioloop.IOLoop.instance().add_timeout(self._timeout+time(), clbk)

