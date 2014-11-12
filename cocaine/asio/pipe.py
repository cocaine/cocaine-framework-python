import errno
import functools
import logging
import os
import socket
import fcntl
import time

from cocaine.asio.ev import Loop
from cocaine.asio.exceptions import *
from cocaine.futures import Deferred

__author__ = 'Evgeny Safronov <division494@gmail.com>'


log = logging.getLogger(__name__)


class Pipe(object):
    NOT_CONNECTED, CONNECTING, CONNECTED = range(3)

    def __init__(self, sock, ioLoop=None):
        self.address = None

        self.sock = sock
        self.sock.setblocking(False)
        if self.sock.type == socket.SOL_TCP:
            self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        fcntl.fcntl(self.sock.fileno(), fcntl.F_SETFD, fcntl.FD_CLOEXEC)

        self._ioLoop = ioLoop or Loop.instance()

        self._state = self.NOT_CONNECTED
        self._onConnectedDeferred = None
        self._connectionTimeoutTuple = None

    def fileno(self):
        return self.sock.fileno()

    def isConnected(self):
        return self._state == self.CONNECTED

    def isConnecting(self):
        return self._state == self.CONNECTING

    def connect(self, address, timeout=None, blocking=False):
        if self.isConnecting():
            return self._onConnectedDeferred

        if self.isConnected():
            raise IllegalStateError('already connected')

        self._onConnectedDeferred = Deferred()
        self._state = self.CONNECTING
        if blocking:
            return self._blockingConnect(address, timeout)
        else:
            return self._nonBlockingConnect(address, timeout)

    def _blockingConnect(self, address, timeout=None):
        try:
            self.sock.settimeout(timeout)
            self.sock.connect(address)
            self.address = address
            self._state = self.CONNECTED
        except socket.error as err:
            if err.errno == errno.ECONNREFUSED:
                raise ConnectionRefusedError(address)
            elif err.errno == errno.ETIMEDOUT:
                raise ConnectionTimeoutError(address, timeout)
            else:
                raise ConnectionError(address, err)
        finally:
            self.sock.setblocking(False)

    def _nonBlockingConnect(self, address, timeout):
        try:
            self.sock.connect(address)
        except socket.error as err:
            if err.errno in (errno.EINPROGRESS, errno.EWOULDBLOCK):
                callback = functools.partial(self._onConnectedCallback, address)
                self._ioLoop.add_handler(self.sock.fileno(), callback, self._ioLoop.WRITE)
                if timeout:
                    start = time.time()
                    errorback = functools.partial(self._onConnectionTimeout, address)
                    timeoutId = self._ioLoop.add_timeout(start + timeout, errorback)
                    self._connectionTimeoutTuple = timeoutId, start, timeout
            else:
                log.warning('connect error on fd {0}: {1}'.format(self.sock.fileno(), err))
                self.close()
                self._ioLoop.add_callback(lambda: self._onConnectedDeferred.error(ConnectionError(address, err)))
        return self._onConnectedDeferred

    def close(self):
        if self._state == self.NOT_CONNECTED:
            return
        self._state = self.NOT_CONNECTED
        self.address = None
        self._ioLoop.stop_listening(self.sock.fileno())
        self.sock.close()

    def _onConnectionTimeout(self, address):
        if self._connectionTimeoutTuple:
            timeoutId, start, timeout = self._connectionTimeoutTuple
            self._ioLoop.remove_timeout(timeoutId)
            self._connectionTimeoutTuple = None
            self.close()
            df = self._onConnectedDeferred
            self._onConnectedDeferred = None
            df.error(ConnectionTimeoutError(address, timeout))

    def _onConnectedCallback(self, address, fd, event):
        assert fd == self.sock.fileno(), 'Incoming fd must be socket fd'
        assert (event & self._ioLoop.WRITE) or (event & self._ioLoop.ERROR), 'Event must be either write or error'

        def removeConnectionTimeout():
            if self._connectionTimeoutTuple:
                fd, start, timeout = self._connectionTimeoutTuple
                self._ioLoop.remove_timeout(fd)
                self._connectionTimeoutTuple = None

        df = self._onConnectedDeferred
        self._onConnectedDeferred = None
        err = self.sock.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
        if err == 0:
            self._state = self.CONNECTED
            self.address = address
            removeConnectionTimeout()
            self._ioLoop.stop_listening(self.sock.fileno())
            df.trigger(None)
        elif err not in (errno.EINPROGRESS, errno.EAGAIN, errno.EALREADY):
            self.close()
            removeConnectionTimeout()
            df.error(ConnectionError(address, os.strerror(err)))

    def read(self, buff, size):
        return self._handle(self.sock.recv_into, buff, size)

    def write(self, buff):
        return self._handle(self.sock.send, buff)

    def _handle(self, func, *args):
        try:
            return func(*args)
        except socket.error as e:
            if e.errno in (errno.EAGAIN, errno.EWOULDBLOCK):
                return 0
            elif e.errno in (errno.ECONNRESET, errno.ECONNABORTED, errno.EPIPE):
                self.close()
                return 0
            else:
                raise

    def __del__(self):
        self.close()
