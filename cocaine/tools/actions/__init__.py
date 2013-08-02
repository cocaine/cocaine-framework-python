import json
import socket
import errno
import tarfile
import msgpack

from cocaine.asio.ng.exceptions import ConnectionError, ConnectionRefusedError
from cocaine.services import Service
from cocaine.tools import log

__author__ = 'Evgeny Safronov <division494@gmail.com>'


def isJsonValid(text):
    try:
        json.loads(text)
        return True
    except ValueError:
        return False


def readArchive(filename):
    if not tarfile.is_tarfile(filename):
        raise tarfile.TarError('File "{0}" is not tar file'.format(filename))
    with open(filename, 'rb') as archive:
        return archive.read()


class CocaineConfigReader:
    @classmethod
    def load(cls, context):
        if isinstance(context, dict):
            log.debug('Content specified directly by dict')
            return msgpack.dumps(context)

        if isJsonValid(context):
            log.debug('Content specified directly by string')
            content = context
        else:
            log.debug('Loading content from file ...')
            with open(context, 'rb') as fh:
                content = fh.read()
        return msgpack.dumps(json.loads(content))


class Storage(object):
    def __init__(self, storage=None):
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
    def __init__(self, key, tags, storage):
        super(List, self).__init__(storage)
        self.key = key
        self.tags = tags

    def execute(self):
        return self.storage.find(self.key, self.tags)