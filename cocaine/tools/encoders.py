import json
import tarfile
import msgpack

from cocaine.exceptions import CocaineError

__author__ = 'Evgeny Safronov <division494@gmail.com>'


def isJsonValid(text):
    try:
        json.loads(text)
        return True
    except ValueError:
        return False


class JsonEncoder(object):
    def encode(self, filename):
        """
        Tries to read json file with name 'filename' and to encode it with msgpack.

        :param filename: file name that need to be encoded
        :raises IOError: if file does not exists, you have not enough permissions to read it or something else
        :raises CocaineError: if file successfully read but cannot be parsed with json parser
        """
        try:
            with open(filename, 'rb') as fh:
                content = fh.read()
                data = json.loads(content)
                encoded = msgpack.packb(data)
                return encoded
        except IOError as err:
            raise CocaineError('Unable to open file - {0}'.format(err))
        except ValueError as err:
            raise CocaineError('File "{0}" is corrupted - {1}'.format(filename, err))


class PackageEncoder(object):
    def encode(self, filename):
        try:
            if not tarfile.is_tarfile(filename):
                raise CocaineError('File "{0}" is ot tar file'.format(filename))
            with open(filename, 'rb') as archive:
                package = msgpack.packb(archive.read())
                return package
        except IOError as err:
            raise CocaineError('Error occurred while reading archive file "{0}" - {1}'.format(filename, err))


def readArchive(filename):
    if not tarfile.is_tarfile(filename):
        raise tarfile.TarError('File "{0}" is not tar file'.format(filename))
    with open(filename, 'rb') as archive:
        package = msgpack.packb(archive.read())
        return package