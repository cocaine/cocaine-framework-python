__author__ = 'EvgenySafronov <division494@gmail.com>'


class Error(Exception):
    pass


class UploadError(Error):
    pass


class ServiceCallError(Error):
    def __init__(self, service, reason):
        super(ServiceCallError, self).__init__('error in service "{0}" - {1}'.format(service, reason))