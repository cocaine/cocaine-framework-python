#
#    Copyright (c) 2012+ Anton Tyurin <noxiouz@yandex.ru>
#    Copyright (c) 2013+ Evgeny Safronov <division494@gmail.com>
#    Copyright (c) 2011-2014 Other contributors as noted in the AUTHORS file.
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

import os
import sys
import threading


class Disowned(Exception):
    pass


class DisownTimer(object):
    def __init__(self, timeout):
        self.cv = threading.Condition()
        self.thread = threading.Thread(target=self.loop,
                                       args=(timeout,), name="disownwatcher")
        self.thread.setDaemon(True)
        self.state = False
        self.interrupted = False

    def start(self):
        self.thread.start()

    def stop(self):
        self.interrupted = True

    def terminate(self):
        # It's the only reliable
        # mechanism to stop the main thread.
        # As thread.interrupt_main() sends KeyboardInterrupt
        # it can't interrupt time.sleep or lock.acquire()
        sys.stderr.write('disowned')
        os._exit(100)
        # ToDo: think about
        # self killing by os.kill

    def loop(self, timeout):
        try:
            while True:
                self._loop(timeout)
        except Disowned:
            if self.interrupted:
                # we were stopped by someone
                return

            self.terminate()

    def _loop(self, timeout):
        with self.cv:
            self.cv.wait(timeout)
            # the flag hasnot been set true
            if not self.state:
                raise Disowned("disowned")
            self.state = False

    def notify(self):
        with self.cv:
            self.state = True
            self.cv.notify()
