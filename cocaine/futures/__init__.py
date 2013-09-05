from cocaine.exceptions import ChokeEvent


CLOSED_STATE_MESSAGE = 'invalid future object state - triggered while in closed state. Fix your code'


class Future(object):
    UNITIALIZED, BOUND, CLOSED = range(3)

    def __init__(self):
        self._callback = None
        self._chunks = []

        self._errorback = None
        self._errors = []

        self.state = self.UNITIALIZED

    def bind(self, callback, errorback=None):
        assert self.state in (self.UNITIALIZED, self.CLOSED), 'double bind is prohibited by design'
        if errorback is None:
            errorback = self._default_errorback

        while self._chunks:
            callback(self._chunks.pop(0))
        while self._errors:
            errorback(self._errors.pop(0))

        if self.state == self.UNITIALIZED:
            self._callback = callback
            self._errorback = errorback
            self.state = self.BOUND

    def unbind(self):
        self._callback = None
        self._errorback = None
        self.state = self.UNITIALIZED

    def close(self, silent=False):
        if self.state == self.CLOSED:
            return

        if not silent:
            if self._errorback is None:
                self._errors.append(ChokeEvent())
            else:
                self._errorback(ChokeEvent())
        self._callback = None
        self._errorback = None
        self.state = self.CLOSED

    def trigger(self, chunk):
        assert self.state in (self.UNITIALIZED, self.BOUND), CLOSED_STATE_MESSAGE
        if self._callback is None:
            self._chunks.append(chunk)
        else:
            self._callback(chunk)

    def error(self, err):
        assert self.state in (self.UNITIALIZED, self.BOUND), CLOSED_STATE_MESSAGE
        if self._errorback is None:
            self._errors.append(err)
        else:
            self._errorback(err)

    def _default_errorback(self, err):
        print('Can\'t throw error without errorback %s' % str(err))


class Sleep(object):
    """ Allow to attach callback, which will be executed after giving period (in fact, not early).
    """

    def __init__(self, timeout):
        self._timeout = timeout

    def bind(self, callback, errorback=None, on_done=None):
        raise NotImplementedError('broken')


class NextTick(object):
    """ Allow to attach callback, which will be executed on the next iteration of reactor loop.

    It's useful for hard operations, using that from handle to avoid event loop blocking.
    """

    def __init__(self):
        pass

    def bind(self, callback, errorback=None, on_done=None):
        raise NotImplementedError('broken')
