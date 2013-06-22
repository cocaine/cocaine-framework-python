# encoding: utf-8
#
#    Copyright (c) 2011-2013 Anton Tyurin <noxiouz@yandex.ru>
#    Copyright (c) 2011-2013 Other contributors as noted in the AUTHORS file.
#
#    This file is part of Cocaine.
#
#    Cocaine is free software; you can redistribute it and/or modify
#    it under the terms of the GNU Lesser General Public License as published by
#    the Free Software Foundation; either version 3 of the License, or
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

import socket
import fcntl
import errno
import types

class Pipe(object):

    def __init__(self, path, on_disconnect_clb=None):
        if isinstance(path, types.TupleType):
            _type = TCP
        elif isinstance(path, types.StringType):
            _type = UNIX
        else:
            raise Exception("Invalid connection path type")
        self.sock = _type.get_socket(path)
        self._connected = True
        assert(on_disconnect_clb is None or callable(on_disconnect_clb))
        self._on_disconnect = on_disconnect_clb or (lambda : None)

    def read(self, buff, size):
        return self.sock.recv_into(buff, size)

    def write(self, buff):
        try:
            return self.sock.send(buff)
        except socket.error as e:
            if e.errno == errno.EPIPE:
                self.connected = False
                return 0

    def fileno(self):
        return self.sock.fileno()

    @property
    def connected(self):
        return self._connected

    @connected.setter
    def connected(self, value):
        self._connected = value
        if False == value:
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
    def get_socket(path, **kwargs):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        TCP.configure(sock)
        while True:
            try:
                sock.connect(path)
            except socket.error as e:
                # The specified socket is connection-mode and is already connected.
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
                    raise
            else:
                break
        return sock

    @staticmethod
    def configure(sock):
        sock.setblocking(0)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        fcntl.fcntl(sock.fileno(), fcntl.F_SETFD, fcntl.FD_CLOEXEC)


class UNIX(object):

    __slots__ = ('get_socket', 'configure')

    @staticmethod
    def get_socket(path, **kwargs):
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        UNIX.configure(sock)
        sock.connect(path)
        return sock

    @staticmethod
    def configure(sock):
        sock.setblocking(0)
        fcntl.fcntl(sock.fileno(), fcntl.F_SETFD, fcntl.FD_CLOEXEC)

