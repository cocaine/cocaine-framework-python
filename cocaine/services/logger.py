#
#    Copyright (c) 2013+ Evgeny Safronov <division494@gmail.com>
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

import collections
import time
import sys

from tornado.ioloop import IOLoop

from .. import concurrent
from ..logging.message import RPC
from ..utils import ThreadLocalMixin

from .service import Service
from .state import RootState

__author__ = 'Evgeny Safronov <division494@gmail.com>'


class Logger(Service, ThreadLocalMixin):
    ROOT_STATE = RootState()

    def __init__(self, app=None):
        super(Logger, self).__init__('logging')
        self.target = self.init_target(app)
        self._verbosity = 0
        self._max_buffer_len = 256
        self._queue = collections.deque(maxlen=self._max_buffer_len)
        self.connect().add_callback(self._init)

    def _init(self, future):
        try:
            future.get()
        except Exception as err:
            print('cannot connect to logger service: {0}'.format(err))
            print('will try again in 1 sec')
            IOLoop.instance().add_timeout(time.time() + 1.0, lambda: self.connect().add_callback(self._init))
        else:
            self.configure()

    @concurrent.engine
    def configure(self):
        try:
            self._verbosity = yield self._invoke(RPC.VERBOSITY, self.ROOT_STATE)
        except Exception as err:
            print('cannot resolve "verbosity" property: {0}'.format(err))
            print('will try again after 1 sec')
            IOLoop.instance().add_timeout(time.time() + 1.0, self.configure)

    @staticmethod
    def init_target(app):
        if not app:
            try:
                app = sys.argv[sys.argv.index('--app') + 1]
            except ValueError:
                app = 'standalone'
        return 'app/{0}'.format(app)

    def emit(self, level, message):
        if level <= self._verbosity:
            while self._queue:
                level, message = self._queue.popleft()
                self._invoke(RPC.EMIT, self.ROOT_STATE, level, self.target, message)
            self._invoke(RPC.EMIT, self.ROOT_STATE, level, self.target, message)
        else:
            if len(self._queue) == self._max_buffer_len:
                print('log message dropped because of queue limit: {0}'.format(message))
            self._queue.append((level, message))
