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


from cocaine.worker import Worker

from tornado import gen
from nose import tools


@tools.raises(ValueError)
def test_worker_wrong_timeouts():
    Worker(heartbeat_timeout=1, disown_timeout=2)


@tools.raises(ValueError)
def test_worker_missing_args():
    Worker()


def test_worker():

    @gen.coroutine
    def ping(request, response):
        print 1
        inc = yield request.read()
        print 2, inc
        response.write("A")
        print 3
        response.close()

    kwargs = {"app": "testapp",
              "endpoint": "tests/enp",
              "uuid": "dsdsddsd"}
    w = Worker(**kwargs)
    w.on("ping", ping)
    w.run()
