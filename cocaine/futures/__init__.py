from time import time
from tornado import ioloop


class Future(object):

    def __init__(self):
        self._clbk = None
        self._errbk = None
        self._on_done = None
        self._errmsg = None
        self._on_done_is_emited = False
        self.cache = list()
        self._state = 1
        self._is_raised_error = False # Flag for on_done callback

    def callback(self, chunk):
        if self._clbk is None:
            self.cache.append(chunk)
        else:
            temp = self._clbk
            self._clbk = None
            temp(chunk)

    def error(self, err):
        self._is_raised_error = True # Flag for on_done callback
        if self._errbk is None:
            self._errmsg = err
        else:
            temp = self._errbk
            self._errbk = None
            temp(err)

    def default_errorback(self, err):
        print "Can't throw error without errorback %s" % str(err)

    def default_on_done(self):
        pass

    def close(self):
        self._state = None
        if len(self.cache) == 0 and self._clbk is not None:
            # No chunks are available at all,
            # then call on_done(), because choke always arrives after all chunks
            if self._on_done is not None and not self._is_raised_error:
                self._on_done()
            elif self._errbk is not None:
                self._errbk(RequestError("No chunks are available"))
            else:
                print("No errorback. Can't throw error")

    def bind(self, callback, errorback=None, on_done=None):
        if len(self.cache) > 0:
            callback(self.cache.pop(0))
        elif self._errmsg is not None:
            if erroback is not None:
                temp = self._errmsg
                self._errmsg = None
                errorback(temp)  # traslate error into worker
            else:
                self.default_errorback(self._errmsg)
        elif self._state is not None:
            self._clbk = callback
            self._errbk = errorback or self.default_errorback
            self._on_done = on_done or self.default_on_done
        elif self._state is None: # Flag for on_done callback
            if on_done is not None:
                on_done()
        # Never reachs this now
        #else:
        #    # Stream closed by choke
        #    # Raise exception here because no chunks
        #    # from cocaine-runtime are availaible
        #    if erroback is not None:
        #        errorback(RequestError("No chunks are available"))
        #    else:
        #        self.default_errorback(RequestError("No chunks are available"))


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
