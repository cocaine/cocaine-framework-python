from cocaine.exceptions import ChokeEvent


CLOSED_STATE_MESSAGE = 'invalid future object state - triggered while in closed state. Fix your code'


class Deferred(object):
    """Encapsulates the result of an asynchronous operation.

    This class represents deferred result of asynchronous operation. In synchronous applications Deferreds are used
    to wait for the result from a thread or process pool. In cocaine they are normally used by yielding them in a
    `engine.asynchronous` context.

    Typical usage assumes that you create `Deferred` object, keep it somewhere, start asynchronous operation and
    return this deferred from function. When asynchronous operation is done, just invoke `trigger` or `error` method
    depending on which type of result you are get, and pass into it.

    Here the example of asynchronous function that starts timer and signals the deferred after 1.0 sec.::

        from tornado.ioloop import IOLoop

        loop = IOLoop.current()

        def timer_function():
            deferred = Deferred()
            timeout = 1.0
            loop.add_timer(time.time() + timeout, lambda: deferred.trigger('Done')
            return deferred

    Now you can use `timer_function` in Engine context::

        result = yield timer_function()

    :ivar state: current object's state. Can be one of the: `UNINITIALIZED`, `BOUND`, `CLOSED`.

    .. note:: All methods in this class are reentrant.
    """
    UNITIALIZED, BOUND, CLOSED = range(3)

    def __init__(self):
        self._callback = None
        self._chunks = []

        self._errorback = None
        self._errors = []

        self.state = self.UNITIALIZED

    def bind(self, callback, errorback=None):
        """Binds callback and errorback to the deferred. Deferred immediately goes into `BOUND` state.

        When bound, deferred will trigger its callback and errorback on any pending value or error respectively.
        If there is no any callback attached to the deferred, it will store them into cache which will be emptied as
        `bind` method invoked.

        :param callback: callback which will be invoked on every pending result.
        :param errorback: errorback which will be invoked on every pending error.

        .. warning:: It's prohibited by design to call this method while deferred is already bounded.
        """
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
        """Unbind deferred and transfer it to the `UNINITIALIZED` state.

        This method drops any previously attached callback or errorback. Therefore, deferred can be used even after
        calling this method - it just need to be rebounded.
        """
        self._callback = None
        self._errorback = None
        self.state = self.UNITIALIZED

    def close(self, silent=False):
        """Close deferred and transfer it to the `CLOSED` state.

        .. note:: It is safe to call this method multiple times.
        .. warning:: After closing Deferred is considered to be dead. Therefore, it can be rebound again.
        """
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
        """Trigger deferred and transfer chunk to the attached callback.

        If there is no callback attached, it will be stored until someone provides it by invoking `bind` method.

        :param chunk: value needed to be transferred.
        """
        assert self.state in (self.UNITIALIZED, self.BOUND), CLOSED_STATE_MESSAGE
        if self._callback is None:
            self._chunks.append(chunk)
        else:
            self._callback(chunk)

    def error(self, err):
        """Trigger deferred and transfer chunk to the attached errorback.

        If there is no errorback attached, it will be stored until someone provides it by invoking `bind` method.

        :param err: error needed to be transferred.
        """
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


# Left for backward compatibility
class Future(Deferred):
    def __init__(self):
        import warnings
        warnings.warn('This class was renamed into `Deferred`', DeprecationWarning)
        super(Future, self).__init__()
