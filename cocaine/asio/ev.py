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

class Loop(object):
    """ Event loop wrapper"""

    def __init__(self, ioloop=None):
        self._ioloop = ioloop or ev.IOLoop.instance()

        self._callbacks = dict()
        self._fd_events = dict()
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
        def dummy(*args):
            pass
        self._ioloop.add_handler(fd, self.proxy, self._ioloop.READ)
        self._fd_events[fd] = self._ioloop.READ
        self._callbacks[(fd, self.READ)] = dummy

    def _register_event(self, fd, event):
        self._fd_events[fd] |= event

    def _unregister_event(self, fd, event):
        self._fd_events[fd] ^= event

    def register_write_event(self, callback, fd):
        self._register_event(fd, self.WRITE)
        self._callbacks[(fd, self.WRITE)] = callback
        return True

    def unregister_write_event(self, fd):
        self._unregister_event(fd, self.WRITE)
        return True

    def register_read_event(self, callback, fd):
        self._register_event(fd, self.READ)
        self._callbacks[(fd, self.READ)] = callback
        return True

    def unregister_read_event(self, fd):
        self._unregister_event(fd, self.READ)
        return True

    def proxy(self, fd, event):
        if event & self.WRITE:
            self._callbacks[(fd, self.WRITE)]()
        elif event & self.READ:
            self._callbacks[(fd, self.READ)]()

    @property
    def ioloop(self):
        return self._ioloop


class Timer(ev.PeriodicCallback):
    """ Timer wrapper """

    def __init__(self, callback, callback_time, io_loop):
        super(Timer, self).__init__(callback, callback_time * 1000, io_loop.ioloop)

