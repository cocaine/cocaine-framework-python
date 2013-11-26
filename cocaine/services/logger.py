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

import sys

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
        self.connect()

    @staticmethod
    def init_target(app):
        if not app:
            try:
                app = sys.argv[sys.argv.index('--app') + 1]
            except ValueError:
                app = 'standalone'
        return 'app/{0}'.format(app)

    def emit(self, level, message, *args):
        return self._invoke(RPC.EMIT, self.ROOT_STATE, level, self.target, message % args)

    def verbosity(self):
        return self._invoke(RPC.VERBOSITY, self.ROOT_STATE)

