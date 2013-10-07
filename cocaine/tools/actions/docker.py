import json
import tarfile
import StringIO
import urllib

from tornado.httpclient import AsyncHTTPClient, HTTPRequest
from tornado.ioloop import IOLoop

from cocaine.tools import log
from cocaine.futures import chain
from cocaine.tools.helpers._unix import AsyncUnixHTTPClient

__author__ = 'Evgeny Safronov <division494@gmail.com>'

DEFAULT_TIMEOUT = 120.0
DEFAULT_URL = 'unix://var/run/docker.sock'
DEFAULT_VERSION = '1.4'
DEFAULT_INDEX_URL = 'https://index.docker.io/v1/'


def expand_registry_url(hostname):
    if hostname.startswith('http:') or hostname.startswith('https:'):
        if '/' not in hostname[9:]:
            hostname += '/v1/'
        return hostname
    return 'http://' + hostname + '/v1/'


def resolve_repository_name(fullname):
    if '://' in fullname:
        raise ValueError('repository name can not contain a scheme ({0})'.format(fullname))

    parts = fullname.split('/', 1)
    if not '.' in parts[0] and not ':' in parts[0] and parts[0] != 'localhost':
        return DEFAULT_INDEX_URL, fullname

    if len(parts) < 2:
        raise ValueError('invalid repository name ({0})'.format(fullname))

    if 'index.docker.io' in parts[0]:
        raise ValueError('invalid repository name, try "{0}" instead'.format(parts[1]))

    return expand_registry_url(parts[0]), parts[1]


class Client(object):
    def __init__(self, url=DEFAULT_URL, version=DEFAULT_VERSION, timeout=DEFAULT_TIMEOUT, io_loop=None):
        self.url = url
        self.version = version
        self.timeout = timeout
        self._io_loop = io_loop
        self.config = {
            'url': url,
            'version': version,
            'timeout': timeout,
            'io_loop': io_loop
        }

    def info(self):
        return Info(**self.config).execute()

    def images(self):
        return Images(**self.config).execute()

    def containers(self):
        return Containers(**self.config).execute()

    def build(self, path, tag=None, quiet=False, streaming=None):
        return Build(path, tag, quiet, streaming, **self.config).execute()

    def push(self, name, auth, streaming=None):
        return Push(name, auth, streaming, **self.config).execute()


class Action(object):
    def __init__(self, url, version, timeout=DEFAULT_TIMEOUT, io_loop=None):
        self._unix = url.startswith('unix://')
        self._version = version
        self.timeout = timeout
        self._io_loop = io_loop
        if self._unix:
            self._base_url = url
            self._http_client = AsyncUnixHTTPClient(self._io_loop, url)
        else:
            self._base_url = '{0}/v{1}'.format(url, version)
            self._http_client = AsyncHTTPClient(self._io_loop)

    def execute(self):
        raise NotImplementedError

    def _make_url(self, path, query=None):
        if query is not None:
            query = dict((k, v) for k, v, in query.iteritems() if v is not None)
            return '{0}{1}?{2}'.format(self._base_url, path, urllib.urlencode(query))
        else:
            return '{0}{1}'.format(self._base_url, path)


class Info(Action):
    @chain.source
    def execute(self):
        response = yield self._http_client.fetch(self._make_url('/info'))
        yield response.body


class Images(Action):
    @chain.source
    def execute(self):
        response = yield self._http_client.fetch(self._make_url('/images/json'))
        yield response.body


class Containers(Action):
    @chain.source
    def execute(self):
        response = yield self._http_client.fetch(self._make_url('/containers/json'))
        yield json.loads(response.body)


class Build(Action):
    def __init__(self, path, tag=None, quiet=False, streaming=None,
                 url='unix://var/run/docker.sock', version='1.4', timeout=DEFAULT_TIMEOUT, io_loop=None):
        super(Build, self).__init__(url, version, timeout, io_loop)
        self._path = path
        self._tag = tag
        self._quiet = quiet
        self._streaming = streaming
        self._io_loop = io_loop or IOLoop.current()

    @chain.source
    def execute(self):
        headers = None
        body = None
        remote = None

        if any(map(self._path.startswith, ['http://', 'https://', 'git://', 'github.com/'])):
            log.info('Remote url detected: "%s"', self._path)
            remote = self._path
        else:
            log.info('Local path detected. Creating archive "%s"... ', self._path)
            headers = {'Content-Type': 'application/tar'}
            body = self._tar(self._path)
            log.info('OK')

        query = {'t': self._tag, 'remote': remote, 'q': self._quiet}
        url = self._make_url('/build', query)
        log.info('Building "%s"... ', url)
        request = HTTPRequest(url,
                              method='POST', headers=headers, body=body,
                              request_timeout=self.timeout,
                              streaming_callback=self._streaming)
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


class Push(Action):
    def __init__(self, name, auth, streaming=None,
                 url='unix://var/run/docker.sock', version='1.4', timeout=DEFAULT_TIMEOUT, io_loop=None):
        self.name = name
        self.auth = auth
        self._streaming = streaming
        super(Push, self).__init__(url, version, timeout, io_loop)

    @chain.source
    def execute(self):
        url = self._make_url('/images/{0}/push'.format(self.name))
        registry, name = resolve_repository_name(self.name)

        body = json.dumps(self.auth)
        log.info('Pushing "%s" into "%s"... ', name, registry)
        request = HTTPRequest(url, method='POST', body=body,
                              request_timeout=self.timeout,
                              streaming_callback=self._on_body)
        try:
            yield self._http_client.fetch(request)
            log.info('OK')
        except Exception as err:
            log.error('FAIL - %s', err)
            raise err

    def _on_body(self, data):
        try:
            self._streaming(json.loads(data)['status'])
        except Exception as err:
            self._streaming(str(err))