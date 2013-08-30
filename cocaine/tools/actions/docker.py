import tarfile
import StringIO

from tornado.httpclient import AsyncHTTPClient, HTTPRequest
from tornado.ioloop import IOLoop

from cocaine.tools import log
from cocaine.futures import chain
from cocaine.tools.helpers._unix import AsyncUnixHTTPClient

__author__ = 'Evgeny Safronov <division494@gmail.com>'


class Client(object):
    def __init__(self, url='unix://var/run/docker.sock', version='1.4', io_loop=None):
        self.url = url
        self.version = version
        self._io_loop = io_loop

    def info(self):
        return Info(self.url, self.version, self._io_loop).execute()

    def images(self):
        return Images(self.url, self.version, self._io_loop).execute()

    def build(self, path, tag=None, quiet=False, streaming=None, timeout=120.0):
        return Build(path, tag, quiet, streaming, timeout, self.url, self.version, self._io_loop).execute()


class Action(object):
    def __init__(self, url, version, io_loop=None):
        self._unix = url.startswith('unix://')
        self._version = version
        self._io_loop = io_loop
        if self._unix:
            self._base_url = url
            self._http_client = AsyncUnixHTTPClient(self._io_loop, url)
        else:
            self._base_url = '{0}/v{1}'.format(url, version)
            self._http_client = AsyncHTTPClient(self._io_loop)

    def execute(self):
        raise NotImplementedError

    def _url(self, path):
        return '{0}{1}'.format(self._base_url, path)


class Info(Action):
    @chain.source
    def execute(self):
        response = yield self._http_client.fetch(self._url('/info'))
        yield response.body


class Images(Action):
    @chain.source
    def execute(self):
        response = yield self._http_client.fetch(self._url('/images/json'))
        yield response.body


class Build(Action):
    def __init__(self, path, tag=None, quiet=False, streaming=None, timeout=120.0, url='unix://var/run/docker.sock',
                 version='1.4', io_loop=None):
        super(Build, self).__init__(url, version, io_loop)
        self._path = path
        self._tag = tag
        self._quiet = quiet
        self._streaming = streaming
        self._timeout = timeout
        self._io_loop = io_loop or IOLoop.current()

    @chain.source
    def execute(self):
        headers = None
        data = None
        remote = None

        if any(map(self._path.startswith, ['http://', 'https://', 'git://', 'github.com/'])):
            log.info('Remote url detected: "%s"', self._path)
            remote = self._path
        else:
            log.info('Local path detected. Creating archive "%s" ...', self._path)
            headers = {'Content-Type': 'application/tar'}
            data = self._tar(self._path)
            log.info('OK')

        query = {'tag': self._tag, 'remote': remote, 'q': self._quiet}
        url = self._url('/build')
        log.info('Building "%s" ...', url)
        request = HTTPRequest(url, method='POST', headers=headers, body=data, request_timeout=self._timeout)
        if self._streaming is not None:
            request.streaming_callback = self._streaming
        try:
            yield self._http_client.fetch(request)
            log.info('OK')
        except Exception as err:
            log.error('FAIL - %s', err)
            raise err

    def _tar(self, path):
        stream = StringIO.StringIO()
        try:
            tar = tarfile.open(mode='w', fileobj=stream)
            tar.add(path, arcname='.')
            return stream.getvalue()
        finally:
            stream.close()