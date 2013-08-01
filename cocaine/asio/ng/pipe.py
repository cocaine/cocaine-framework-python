import errno
import logging
import os
import socket
import fcntl
import time
from cocaine.exceptions import ConnectionError
from cocaine.futures.chain import FutureCallableMock, FutureResult
from cocaine.asio.ev import Loop

__author__ = 'Evgeny Safronov <division494@gmail.com>'


log = logging.getLogger(__name__)


class ConnectionFailedError(ConnectionError):
    pass


class IllegalStateError(ConnectionError):
    pass


class TimeoutError(ConnectionError):
    def __init__(self, timeout):
        super(TimeoutError, self).__init__('timeout ({0}s)'.format(timeout))


class Pipe(object):
    NOT_CONNECTED, CONNECTING, CONNECTED = range(3)

    def __init__(self, sock):
        self.sock = sock
        self.sock.setblocking(False)
        if self.sock.family == socket.SOCK_STREAM:
            self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        fcntl.fcntl(self.sock.fileno(), fcntl.F_SETFD, fcntl.FD_CLOEXEC)

        #todo: Inject loop
        self._ioLoop = Loop.instance()

        self._state = self.NOT_CONNECTED
        self._onConnectedDeferred = FutureCallableMock()
        self._connectionTimeoutTuple = None

    def fileno(self):
        return self.sock.fileno()

    def isConnected(self):
        return self._state == self.CONNECTED

    def isConnecting(self):
        return self._state == self.CONNECTING

    def connect(self, address, timeout=None):
        if self.isConnecting():
            return self._onConnectedDeferred

        if self.isConnected():
            raise IllegalStateError('already connected')

        if timeout is not None and timeout < 0.001:
            raise ValueError('timeout must be >= 1 ms.')

        self._state = self.CONNECTING
        try:
            self.sock.connect(address)
        except socket.error as err:
            if err.errno in (errno.EINPROGRESS, errno.EWOULDBLOCK):
                self._ioLoop.add_handler(self.sock.fileno(), self._onConnectedCallback, self._ioLoop.WRITE)
                if timeout:
                    start = time.time()
                    fd = self._ioLoop.add_timeout(start + timeout, self._onConnectionTimeout)
                    self._connectionTimeoutTuple = fd, start, timeout
            else:
                log.warning('connect error on fd {0}: {1}'.format(self.sock.fileno(), err))
                self.close()
                self._ioLoop.add_callback(lambda: self._onConnectedDeferred.ready(ConnectionFailedError(err)))
        return self._onConnectedDeferred

    def close(self):
        if self._state == self.CONNECTED:
            self._state = self.NOT_CONNECTED
            self.sock.close()
            self.sock = None

    def _onConnectionTimeout(self):
        if self._connectionTimeoutTuple:
            fd, start, timeout = self._connectionTimeoutTuple
            self._ioLoop.remove_timeout(fd)
            self._connectionTimeoutTuple = None
            self._ioLoop.stop_listening(self.sock.fileno())
            self.close()
            self._onConnectedDeferred.ready(FutureResult(TimeoutError(timeout)))

    def _onConnectedCallback(self, fd, event):
        assert fd == self.sock.fileno(), 'Incoming fd must be socket fd'
        assert event in (self._ioLoop.WRITE, self._ioLoop.ERROR), 'Event must be either write or error'

        def removeConnectionTimeout():
            if self._connectionTimeoutTuple:
                fd, start, timeout = self._connectionTimeoutTuple
                self._ioLoop.remove_timeout(fd)
                self._connectionTimeoutTuple = None

        err = self.sock.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
        if err == 0:
            self._state = self.CONNECTED
            removeConnectionTimeout()
            self._ioLoop.stop_listening(self.sock.fileno())
            self._onConnectedDeferred.ready()
        elif err not in (errno.EINPROGRESS, errno.EAGAIN, errno.EALREADY):
            self.close()
            removeConnectionTimeout()
            self._ioLoop.stop_listening(self.sock.fileno())
            self._onConnectedDeferred.ready(ConnectionFailedError(os.strerror(err)))

    def read(self, buff, size):
        try:
            return self.sock.recv_into(buff, size)
        except socket.error as e:
            if e.errno in (errno.ECONNRESET, errno.ECONNABORTED, errno.EPIPE):
                self.close()
                return 0
            elif e.errno in (errno.EAGAIN, errno.EWOULDBLOCK):
                return 0
            else:
                raise

    def write(self, buff):
        try:
            return self.sock.send(buff)
        except socket.error as e:
            if e.errno in (errno.EWOULDBLOCK, errno.EAGAIN):
                return 0
            elif e.errno in (errno.ECONNRESET, errno.ECONNABORTED, errno.EPIPE):
                self.close()
                return 0
            else:
                raise

    @property
    def connected(self):
        return self._state == self.CONNECTED