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


from threading import Lock

from tornado import ioloop as ev


class Loop(object):
    """Event loop wrapper for inner usage. Normally you should use `tornado.IOLoop.current()`.
    """

    _instance_lock = Lock()  # Lock for instance method

    def __init__(self, ioloop=None):
        self._ioloop = ioloop or ev.IOLoop.current()

        self._callbacks = dict()
        self._fd_events = dict()

        # Tornado ERROR = epoll._ERROR | epoll._EPOLLHUP
        self.READ = self._ioloop.READ
        self.ERROR = self._ioloop.ERROR
        self.WRITE = self._ioloop.WRITE

        # Aliases
        self.add_handler = self._ioloop.add_handler
        self.add_timeout = self._ioloop.add_timeout
        self.remove_timeout = self._ioloop.remove_timeout
        self.add_callback = self._ioloop.add_callback

    @staticmethod
    def instance():
        if not hasattr(Loop, "_instance"):
            with Loop._instance_lock:
                if not hasattr(Loop, "_instance"):
                    Loop._instance = Loop()
        return Loop._instance

    def run(self):
        self._ioloop.start()

    def run_for_time(self, timeout):
        from time import time
        self._ioloop.add_timeout(time() + timeout, self._on_timeout)
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
        self._ioloop.update_handler(fd, self._fd_events[fd])

    def _unregister_event(self, fd, event):
        self._fd_events[fd] ^= event
        self._ioloop.update_handler(fd, self._fd_events[fd])

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

    def stop_listening(self, fd):
        self._ioloop.remove_handler(fd)
        self._callbacks.pop((fd, self.READ), None)
        self._callbacks.pop((fd, self.WRITE), None)
        self._fd_events.pop(fd, None)
        return True

    def proxy(self, fd, event):
        if event & self.WRITE:
            self._callbacks[(fd, self.WRITE)]()
        if event & self.READ:
            self._callbacks[(fd, self.READ)]()

    @property
    def ioloop(self):
        return self._ioloop

    @property
    def fds(self):
        return self._fd_events.keys()


class Timer(ev.PeriodicCallback):
    def __init__(self, callback, callback_time, io_loop):
        super(Timer, self).__init__(callback, callback_time * 1000, io_loop.ioloop)
