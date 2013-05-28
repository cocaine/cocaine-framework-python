#TODO: Duplicate exception classes here with compare to cocaine.exceptions module.
# May be merge it?


class Error(Exception):
    pass


class ConnectionError(Error):
    pass


class ConnectionRefusedError(ConnectionError):
    def __init__(self, host, port):
        message = 'Invalid cocaine-runtime endpoint: {host}:{port}'.format(host=host, port=port)
        super(ConnectionRefusedError, self).__init__(message)
