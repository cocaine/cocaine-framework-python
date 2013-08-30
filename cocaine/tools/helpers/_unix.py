import socket
from tornado.iostream import IOStream
from tornado.simple_httpclient import _HTTPConnection, SimpleAsyncHTTPClient

__author__ = 'Evgeny Safronov <division494@gmail.com>'


class _UnixHTTPConnection(_HTTPConnection):
    def __init__(self, prefix, io_loop, client, request, release_callback, final_callback, max_buffer_size):
        path = prefix.replace('unix:/', '')
        prefix_id = request.url.index(prefix)
        request.url = 'http://localhost{0}'.format(request.url[prefix_id + len(prefix):])

        class NoneResolver(object):
            def resolve(self, host, port, af, callback):
                io_loop.add_callback(callback, ((socket.AF_UNIX, path),))
        super(_UnixHTTPConnection, self).__init__(io_loop, client, request, release_callback, final_callback,
                                                  max_buffer_size, NoneResolver())
        self.parsed_hostname = prefix

    def _create_stream(self, addrinfo):
        sock = socket.socket(socket.AF_UNIX)
        return IOStream(sock, io_loop=self.io_loop, max_buffer_size=self.max_buffer_size)


class AsyncUnixHTTPClient(SimpleAsyncHTTPClient):
    def __init__(self, io_loop, prefix):
        self._prefix = prefix
        super(AsyncUnixHTTPClient, self).__init__(io_loop)

    def _handle_request(self, request, release_callback, final_callback):
        _UnixHTTPConnection(self._prefix, self.io_loop, self, request, release_callback, final_callback,
                            self.max_buffer_size)
