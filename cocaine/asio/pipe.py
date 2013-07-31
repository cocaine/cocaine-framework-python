# encoding: utf-8
#
#    Copyright (c) 2011-2013 Anton Tyurin <noxiouz@yandex.ru>
#    Copyright (c) 2011-2013 Other contributors as noted in the AUTHORS file.
#
#    This file is part of Cocaine.
#
#    Cocaine is free software; you can redistribute it and/or modify
#    it under the terms of the GNU Lesser General Public License as published
#    by the Free Software Foundation; either version 3 of the License, or
#    (at your option) any later version.
#
#    Cocaine is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#    GNU Lesser General Public License for more details.
#
#    You should have received a copy of the GNU Lesser General Public License
#    along with this program. If not, see <http://www.gnu.org/licenses/>.
#
import logging
import os

import socket
import fcntl
import errno
import types
import time
from functools import partial

from cocaine.futures.chain import FutureCallableMock, FutureResult
from cocaine.asio.ev import Loop
from cocaine.exceptions import AsyncConnectionError
from cocaine.exceptions import AsyncConnectionTimeoutError

__all__ = ["Pipe"]


log = logging.getLogger(__name__)


class ConnectionFailedError(Exception):
    pass


class AlreadyConnectedError(Exception):
    pass


class PipeNG(object):
    def __init__(self, sock):
        self.sock = sock
        self._ioLoop = Loop.instance()

        self._connecting = False
        self._connected = False
        self._onConnectedDeferred = FutureCallableMock()

    def connect(self, endpoint):
        if self._connecting:
            return self._onConnectedDeferred

        if self._connected:
            raise AlreadyConnectedError()

        self._connecting = True
        try:
            self.sock.connect(endpoint)
            self._ioLoop.add_handler(self.sock.fileno(), self._onConnectedCallback, self._ioLoop.WRITE)
        except socket.error as err:
            if err.errno not in (errno.EINPROGRESS, errno.EWOULDBLOCK):
                log.warning('Connect error on fd {0}: {1}'.format(self.sock.fileno(), err))
                self.close()
                deferredCallback = lambda: self._onConnectedDeferred.ready(FutureResult(ConnectionFailedError(err)))
                self._ioLoop.ioloop.add_callback(deferredCallback)

        return self._onConnectedDeferred

    def close(self):
        if self._connected:
            self._connecting = False
            self._connected = False
            self.close_fd()

    def close_fd(self):
        raise NotImplementedError()

    def _onConnectedCallback(self, fd, event):
        assert fd == self.sock.fileno(), 'Incoming fd must be socket fd'
        assert event in (self._ioLoop.WRITE, self._ioLoop.ERROR), 'Event must be either write or error'

        err = self.sock.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
        if err == 0:
            self._connecting = False
            self._connected = True
            self._ioLoop.stop_listening(self.sock.fileno())
            self._onConnectedDeferred.ready(FutureResult(None))
        elif err not in (errno.EINPROGRESS, errno.EAGAIN, errno.EALREADY):
            if self.is_valid_fd():
                self._ioLoop.stop_listening(self.sock.fileno())
                self.sock.close()
            error = socket.error(err, os.strerror(err))
            self._onConnectedDeferred.ready(FutureResult(ConnectionFailedError(error)))

    def is_valid_fd(self):
        if self.sock is None:
            return False
        try:
            self.sock.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
        except socket.error as e:
            if e.errno in (errno.EBADF, errno.ENOTSOCK):
                return False
        return True


class Pipe(object):

    def __init__(self, path, on_disconnect_clb=None):
        if isinstance(path, types.TupleType):
            self.sock = TCP.get_socket()
        elif isinstance(path, types.StringType):
            self.sock = UNIX.get_socket()
        else:
            raise Exception("Invalid connection path type")
        self._connected = False
        self._connection_failed = False  # Implement states for this
        self.path = path
        assert(on_disconnect_clb is None or callable(on_disconnect_clb))
        self._on_disconnect = on_disconnect_clb or (lambda: None)

    def connect(self):
        while True:
            try:
                self.sock.connect(self.path)
            except socket.error as e:
                # The specified socket is connection-mode
                # and is already connected.
                if e.errno == errno.EISCONN:
                    break
                elif e.errno not in (
                    # O_NONBLOCK is set for the file descriptor for the socket
                    # and the connection cannot be immediately established;
                    # the connection shall be established asynchronously.
                    errno.EINPROGRESS, errno.EAGAIN,
                    # A connection request is already
                    # in progress for the specified socket.
                    errno.EALREADY):
                    self.sock.close()
                    raise
            else:
                break
        self.connected = True

    def _on_socket_event(self, ioloop, on_connect_callback, istimeout=False, *args):
        if istimeout:
            # Called with timeout event.
            # Check connection state and connection_failed state
            if not self._connected and not self._connection_failed:
                if self.is_valid_fd:
                    # remove fd from event polling
                    ioloop.stop_listening(self.sock.fileno())
                    # we can't reuse socket - close it
                    self.sock.close()
                # send timeout error as result
                on_connect_callback(ConnectionResult(AsyncConnectionTimeoutError(self.path)))
            return

        err = self.sock.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
        if err == 0:
            # Connect successfully
            self.connected = True
            # remove fd from event polling
            ioloop.stop_listening(self.sock.fileno())
            # remove handler
            on_connect_callback(ConnectionResult())
        elif err not in (errno.EINPROGRESS, errno.EAGAIN, errno.EALREADY):
            # remove fd from event polling
            if self.is_valid_fd:
                ioloop.stop_listening(self.sock.fileno())
                # we can't reuse socket - close it
                self.sock.close()
            self._connection_failed = True
            # send error as result
            on_connect_callback(ConnectionResult(AsyncConnectionError(self.path, errno.errorcode[err])))

    def async_connect(self, on_connect_callback, timeout=None, _ioloop=None):
        ioloop = _ioloop or Loop.instance()
        self.sock.connect_ex(self.path)

        event_handler = partial(self._on_socket_event,
                                ioloop,
                                on_connect_callback)

        ioloop.add_handler(self.sock.fileno(),
                           partial(event_handler, False),
                           ioloop.WRITE)

        if timeout is not None:
            ioloop.add_timeout(time.time() + timeout,
                               partial(event_handler, True))

    def read(self, buff, size):
        try:
            return self.sock.recv_into(buff, size)
        except socket.error as e:
            if e.errno in (errno.ECONNRESET, errno.ECONNABORTED, errno.EPIPE):
                self.connected = False
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
            else:
                if e.errno in (errno.ECONNRESET,
                               errno.ECONNABORTED,
                               errno.EPIPE):
                    # log it
                    self.connected = False
                self.close()
                return 0

    def close(self):
        self.sock.close()
        #self._connected = False

    def fileno(self):
        return self.sock.fileno()

    @property
    def is_valid_fd(self):
        if self.sock is None:
            return False
        try:
            self.sock.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
        except socket.error as e:
            if e.errno in (errno.EBADF, errno.ENOTSOCK):
                return False
        return True

    @property
    def connected(self):
        return self._connected

    @connected.setter
    def connected(self, value):
        self._connected = value
        if not value:
            self._on_disconnect()

    # Next methods are used only perform_sync
    def writeall(self, buff):
        """Only for synchronous calls"""
        return self.sock.sendall(buff)

    def recv(self, length):
        return self.sock.recv(length)

    def settimeout(self, value):
        self.sock.settimeout(value)


class TCP(object):

    __slots__ = ('get_socket', 'configure')

    @staticmethod
    def get_socket():
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        TCP.configure(sock)
        return sock

    @staticmethod
    def configure(sock):
        sock.setblocking(0)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        fcntl.fcntl(sock.fileno(), fcntl.F_SETFD, fcntl.FD_CLOEXEC)


class UNIX(object):

    __slots__ = ('get_socket', 'configure')

    @staticmethod
    def get_socket():
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        UNIX.configure(sock)
        return sock

    @staticmethod
    def configure(sock):
        sock.setblocking(0)
        fcntl.fcntl(sock.fileno(), fcntl.F_SETFD, fcntl.FD_CLOEXEC)


class ConnectionResult(object):

    def __init__(self, error=None):
        if error is not None:
            def res():
                raise error
        else:
            res = lambda: True
        setattr(self, "get", res)
