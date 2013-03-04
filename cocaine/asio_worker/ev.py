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

from tornado import ioloop as ev

from time import time

class Service(object):
    """ Event loop wrapper"""

    def __init__(self, ioloop=None):
        self._ioloop = ioloop or ev.IOLoop.instance()
        self.READ_callbacks = dict()
        self.WRITE_callbacks = dict()
        self.READ = self._ioloop.READ
        self.WRITE = self._ioloop.WRITE

    def run(self):
        self._ioloop.start()

    def run_for_time(self, _timeout):
        from time import time
        self._ioloop.add_timeout(time()+_timeout, self._on_timeout)
        self.run()

    def stop(self):
        self._ioloop.stop()

    def _on_timeout(self):
        self._ioloop.stop()

    def bind_on_fd(self, fd):
        self._ioloop.add_handler(fd, self.proxy, self.READ | self.WRITE)

    def proxy(self, fd, event):
        try:
            if event == self.READ | self.WRITE:
                self.READ_callbacks[fd]()
            elif event == self.WRITE:
                self.WRITE_callbacks[fd]()
        except KeyError:
            pass

    def register_callback(self, callback, fd, event):
        if event == self.READ:
            self.READ_callbacks[fd] = callback
            return True
        elif event == self.WRITE:
            self.WRITE_callbacks[fd] = callback
            return True
        else:
            return False

    def disown_callback(self, callback, fd, event):
        if event == self.READ:
            self.READ_callbacks.pop(fd)
        elif event == self.WRITE:
            self.WRITE_callbacks.pop(fd)

    @property
    def ioloop(self):
        return self._ioloop
#
#
#

class Timer(ev.PeriodicCallback):
    """ Timer wrapper """

    def __init__(self, callback, callback_time, io_loop):
        super(Timer, self).__init__(callback, callback_time * 1000, io_loop.ioloop)

