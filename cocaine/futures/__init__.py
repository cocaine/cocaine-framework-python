from time import time
from cocaine.exceptions import ChokeEvent
from tornado import ioloop


class Future(object):

    def __init__(self):
        self._clbk = None
        self._errbk = None
        self._on_done = None
        self._errmsg = None
        self.cache = list()
        self._state = 1
        self._is_raised_error = False # Flag for on_done callback
        self._is_received_chunk = False # 
        self._done = False #

    def callback(self, chunk):
        self._is_received_chunk = True #
        if self._clbk is None:
            self.cache.append(chunk)
        else:
            temp = self._clbk
            #self._clbk = None
            temp(chunk)

    def error(self, err):
        self._is_raised_error = True # Flag for on_done callback
        if self._errbk is None:
            self._errmsg = err
        else:
            temp = self._errbk
            #self._errbk = None
            temp(err)

    def default_errorback(self, err):
        print "Can't throw error without errorback %s" % str(err)

    def default_on_done(self):
        pass

    def close(self):
        self._state = None
        # print('Future.close', self, self._clbk, self._errbk)
        if self._clbk is None and self._errbk is None:
            self.cache.append(ChokeEvent())
            return

        if not self._is_raised_error:
            self._errbk(ChokeEvent())
            self._done = True
        # if not self._is_raised_error and not self._is_received_chunk:
        #     if self._clbk:
        #         self._clbk(None)
        #     self._done = True

    def bind(self, callback, errorback=None, on_done=None):
        #TODO: Remove commented strings
        # print('Future.bind(start)', self, callback, errorback, self.cache)
        if len(self.cache) > 0: # There are some chunks in cache - return immediatly
            self._clbk = callback
            self._errbk = errorback
            callback(self.cache.pop(0))
        elif self._errmsg is not None: # Error has been received - raise it
            if errorback is not None:
                temp = self._errmsg
                self._errmsg = None
                errorback(temp)  # traslate error into worker
            else:
                self.default_errorback(self._errmsg)
        elif self._state is not None: # There is no data yet - attach callbacks
            self._clbk = callback
            self._errbk = errorback or self.default_errorback
            self._on_done = on_done or self.default_on_done
        elif self._done: # No chunks, but choke has been received
            on_done()
        # print('Future.bind(end)', self, self._clbk, self._errbk)


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
    It's useful for hard operations, using that from handle to avoid
    event loop blocking.
    """

    def __init__(self):
        pass

    def bind(self, callback, errorback=None, on_done=None):
        clbk = callback or on_done or errorback
        ioloop.IOLoop.instance().add_callback(clbk)
