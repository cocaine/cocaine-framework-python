__author__ = 'Evgeny Safronov <division494@gmail.com>'


class ConnectionError(Exception):
    def __init__(self, host, port, reason):
        super(ConnectionError, self).__init__('{0}:{1} - {2}'.format(host, port, reason))


class ConnectionResolveError(ConnectionError):
    def __init__(self, host, port):
        super(ConnectionResolveError, self).__init__(host, port, 'could not resolve hostname "{0}"'.format(host))


class ConnectionRefusedError(ConnectionError):
    def __init__(self, host, port):
        super(ConnectionRefusedError, self).__init__(host, port, 'connection refused')


class ConnectionTimeoutError(ConnectionError):
    def __init__(self, host, port, timeout):
        super(ConnectionTimeoutError, self).__init__(host, port, 'timeout ({0}s)'.format(timeout))


class IllegalStateError(Exception):
    pass


class LocatorResolveError(ConnectionError):
    def __init__(self, name, host, port, reason):
        message = 'unable to resolve API for service "%s" at %s:%d - %s' % (name, host, port, reason)
        super(LocatorResolveError, self).__init__(message)
