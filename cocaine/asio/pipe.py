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



class Pipe(socket.socket):

    def __init__(self, path):
        super(Pipe, self).__init__(socket.AF_UNIX, socket.SOCK_STREAM)
        self._configure()
        self.connect(path)

    def _configure(self):
        self.setblocking(0)
        fcntl.fcntl(self.fileno(), fcntl.F_SETFD, fcntl.FD_CLOEXEC)

    def read(self, buff, size):
        return self.recv_into(buff, size)

    def write(self, buff):
        return self.send(buff)


class ServicePipe(socket.socket):

    def __init__(self, path, on_disconnect_clb=None):
        super(ServicePipe, self).__init__(socket.AF_INET, socket.SOCK_STREAM)
        self._configure()
        while True:
            try:
                self.connect(path)
            except socket.error as e:
                # On Mac OS X it raises this on localhost connection
                if e.errno == errno.EISCONN: # Already connected
                    break
                elif e.errno not in (errno.EINPROGRESS, errno.EAGAIN):
                    raise
            else:
                break
        self._connected = True
        assert(on_disconnect_clb is None or callable(on_disconnect_clb))
        self._on_disconnect = on_disconnect_clb or (lambda : None)

    def _configure(self):
        self.setblocking(0)
        fcntl.fcntl(self.fileno(), fcntl.F_SETFD, fcntl.FD_CLOEXEC)

    def read(self, buff, size):
        return self.recv_into(buff, size)

    def write(self, buff):
        try:
            return self.send(buff)
        except socket.error as e:
            if e.errno == errno.EPIPE:
                self.connected = False
                return 0

    def writeall(self, buff):
        """Only for synchronous calls"""
        return self.sendall(buff)

    @property
    def connected(self):
        return self._connected

    @connected.setter
    def connected(self, value):
        self._connected = value
        if False == value:
            self._on_disconnect()
