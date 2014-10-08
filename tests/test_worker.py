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

from multiprocessing import Process

from nose import tools

from runtime import main
from cocaine.worker import Worker


@tools.raises(ValueError)
def test_worker_wrong_timeouts():
    Worker(heartbeat_timeout=1, disown_timeout=2)


@tools.raises(ValueError)
def test_worker_missing_args():
    Worker()


def test_worker():
    socket_path = "tests/enp"
    t = Process(target=main, args=(socket_path,))

    res = list()

    def ping(request, response):
        res.append(1)
        inc = yield request.read()
        res.append(2)
        res.append(inc)
        with response:
            response.write("A")
            res.append(3)

    def bad_ping(request, response):
        import unreal_package
        del unreal_package

    kwargs = dict(app="testapp",
                  endpoint=socket_path,
                  uuid="randomuuid",
                  disown_timeout=1,
                  heartbeat_timeout=2)
    w = Worker(**kwargs)
    t.start()
    t.join(1)
    w.run({"ping": ping,
           "bad_ping": bad_ping})
    assert res[:4] == [1, 2, 'ping', 3], res[:4]


def test_worker_unable_to_connect():
    socket_path = "tests/enp2"
    kwargs = dict(app="testapp",
                  endpoint=socket_path,
                  uuid="randomuuid",
                  disown_timeout=1,
                  heartbeat_timeout=2)
    w = Worker(**kwargs)
    w.run()
