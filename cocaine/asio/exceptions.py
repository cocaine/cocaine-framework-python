__author__ = 'Evgeny Safronov <division494@gmail.com>'


class Error(Exception):
    pass


class CommunicationError(Error):
    pass


class ConnectionError(CommunicationError):
    def __init__(self, address, reason):
        if len(address) == 2:
            host, port = address[:2]
            message = '{0}:{1} - {2}'.format(host, port, reason)
        elif len(address) == 4:
            host, port, flex, scope = address
            message = '{0}:{1} - {2}'.format(host, port, reason)
        else:
            message = '{0} - {1}'.format(address, reason)
        super(ConnectionError, self).__init__(message)


class ConnectionResolveError(ConnectionError):
    def __init__(self, address):
        super(ConnectionResolveError, self).__init__(address, 'could not resolve hostname "{0}"'.format(address))


class ConnectionRefusedError(ConnectionError):
    def __init__(self, address):
        super(ConnectionRefusedError, self).__init__(address, 'connection refused')


class ConnectionTimeoutError(ConnectionError):
    def __init__(self, address, timeout):
        super(ConnectionTimeoutError, self).__init__(address, 'timeout ({0:.3f}s)'.format(timeout))


class LocatorResolveError(ConnectionError):
    def __init__(self, name, address, reason):
        message = 'unable to resolve API for service "{0}" because {1}'.format(name, reason)
        super(LocatorResolveError, self).__init__(address, message)


class TimeoutError(CommunicationError):
    def __init__(self, timeout):
        super(TimeoutError, self).__init__('timeout ({0:.3f}s)'.format(timeout))


class DisconnectionError(CommunicationError):
    def __init__(self, name):
        super(DisconnectionError, self).__init__('Service {0} has been disconnected'.format(name))


class IllegalStateError(CommunicationError):
    pass
