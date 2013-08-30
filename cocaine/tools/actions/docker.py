import StringIO
import tarfile
import urllib

from tornado.httpclient import AsyncHTTPClient, HTTPRequest
from tornado.ioloop import IOLoop

from cocaine.tools import log
from cocaine.futures import chain

__author__ = 'Evgeny Safronov <division494@gmail.com>'


class Build(object):
    def __init__(self, path, tag=None, quiet=False,
                 streaming=None, timeout=120.0,
                 url='unix://var/run/docker.sock', version='1.4', io_loop=None):
        self._path = path
        self._tag = tag
        self._quiet = quiet
        self._streaming = streaming
        self._timeout = timeout
        self._base_url = '{0}/v{1}'.format(url, version)
        self._version = version
        self._io_loop = io_loop or IOLoop.current()

        self._http_client = AsyncHTTPClient(self._io_loop)

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

        url = self._url('/build', {'tag': self._tag, 'remote': remote, 'q': self._quiet})
        log.debug('Requesting "%s"', url)
        request = HTTPRequest(url, method='POST', headers=headers, body=data, request_timeout=self._timeout)
        if self._streaming is not None:
            request.streaming_callback = self._streaming
        try:
            yield self._http_client.fetch(request)
        except Exception as err:
            raise err

    def _tar(self, path):
        stream = StringIO.StringIO()
        try:
            tar = tarfile.open(mode='w', fileobj=stream)
            tar.add(path, arcname='.')
            return stream.getvalue()
        finally:
            stream.close()

    def _url(self, path, params=None):
        if params is not None:
            params = dict((k, v) for k, v, in params.iteritems() if v is not None)
            return '{0}{1}?{2}'.format(self._base_url, path, urllib.urlencode(params))
        else:
            return '{0}{1}'.format(self._base_url, path)
