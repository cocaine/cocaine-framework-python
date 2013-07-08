import socket
import errno

from cocaine.exceptions import ConnectionRefusedError, ConnectionError
from cocaine.services import Service

__author__ = 'Evgeny Safronov <division494@gmail.com>'


class Storage(object):
    def __init__(self, storage=None, **config):
        self.storage = storage

    def connect(self, host='localhost', port=10053):
        try:
            self.storage = Service('storage', host, port)
        except socket.error as err:
            if err.errno == errno.ECONNREFUSED:
                raise ConnectionRefusedError(host, port)
            else:
                raise ConnectionError('Unknown connection error: {0}'.format(err))

    def execute(self):
        raise NotImplementedError()


class List(Storage):
    """
    Abstract storage action class which main aim is to provide find list action on 'key' and 'tags'.
    For example if key='manifests' and tags=('apps',) this class will try to find applications list
    """
    def __init__(self, key, tags, storage, **config):
        super(List, self).__init__(storage, **config)
        self.key = key
        self.tags = tags

    def execute(self):
        return self.storage.find(self.key, self.tags)