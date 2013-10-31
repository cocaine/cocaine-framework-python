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

import msgpack

from ._log import log

__author__ = 'Evgeny Safronov <division494@gmail.com>'


class Response(object):
    def __init__(self, session, worker):
        self.session = session
        self.worker = worker
        self.closed = False

    def write(self, data):
        if self.closed:
            return log.error('stream is closed', exc_info=True)
        self.worker._send_chunk(self.session, msgpack.dumps(data))

    def close(self):
        if self.closed:
            return log.error('already closed', exc_info=True)
        self.closed = True
        self.worker._send_choke(self.session)

    def error(self, code, message, *args):
        if not self.closed:
            self.worker._send_error(self.session, code, message % args)
            self.close()