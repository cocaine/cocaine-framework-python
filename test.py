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

from tornado.ioloop import IOLoop

from cocaine.services import Service
from cocaine.futures import chain

@chain.source
def do_work(lines):
    try:
        for line in lines:
            result = yield mastermind.enqueue('<event>', '<args>')
            # Process
    except Exception as err:
        print('error occurred: %s', err)
    finally:
        loop.stop()

mastermind = Service('echo')
do_work([line.strip() for line in open('<filename>')])

loop = IOLoop.current()
loop.start()