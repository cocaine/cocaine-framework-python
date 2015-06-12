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

import logging
import sys

from nose import tools

from runtime import main_v0, main_v1, HEADERS, BODY, HTTP_VERSION
from cocaine.worker import Worker
from cocaine.worker.worker import WorkerV1
from cocaine.worker.request import RequestError

from cocaine.decorators import wsgi
from cocaine.decorators import http


log = logging.getLogger("cocaine")
log.setLevel(logging.DEBUG)


@tools.raises(ValueError)
def test_worker_wrong_timeouts():
    Worker(heartbeat_timeout=1, disown_timeout=2)


@tools.raises(ValueError)
def test_worker_missing_args():
    Worker()


def test_worker_v0():
    socket_path = "tests/enp"

    res = list()
    wsgi_res = {"body": list(),
                "status": None,
                "headers": None}

    http_res = {}

    def collector(func):
        def wrapper(environ, start_response):
            def g(func):
                def w(status, headers):
                    wsgi_res["status"] = status
                    wsgi_res["headers"] = headers
                    return func(status, headers)
                return w
            result = func(environ, g(start_response))
            wsgi_res["body"].extend(result)
            return res
        return wrapper

    def ping(request, response):
        res.append(1)
        inc = yield request.read()
        res.append(2)
        res.append(inc)
        with response:
            response.write("A")
            res.append(3)

    def bad_ping(request, response):
        raise Exception("Exception")

    def notclosed(request, response):
        yield request.read()
        response.write("A")

    @collector
    def wsgi_app(environ, start_response):
        response_body = 'Method %s' % environ['REQUEST_METHOD']
        status = '200 OK'
        response_headers = [('Content-Type', 'text/plain'),
                            ('Content-Length', str(len(response_body)))]
        start_response(status, response_headers)
        return [response_body, "A"]

    @http
    def http_test(request, response):
        req = yield request.read()
        http_res["req"] = req
        response.write_head(200, {'Content-Type': 'text/plain'})
        response.write("OK")
        response.close()

    kwargs = dict(app="testapp",
                  endpoint=socket_path,
                  uuid="randomuuid",
                  disown_timeout=1,
                  heartbeat_timeout=2)

    main_v0(socket_path, 10)
    w = Worker(**kwargs)
    w.run({"ping": ping,
           "bad_ping": bad_ping,
           "notclosed": notclosed,
           "http_test": http_test,
           "http": wsgi(wsgi_app)})

    assert res[:4] == [1, 2, 'pong', 3], res[:4]
    assert wsgi_res["body"] == ["Method POST", "A"], wsgi_res
    assert wsgi_res["status"] == '200 OK', wsgi_res
    assert wsgi_res["headers"] == [('Content-Type', 'text/plain'), ('Content-Length', '11')], wsgi_res["headers"]

    req = http_res["req"]

    assert req.body == BODY, req.body
    assert req.headers == dict(HEADERS), req.headers
    assert req.meta["version"] == HTTP_VERSION, req.meta["version"]
    if sys.version_info[0] == 2:
        assert req.request == {'dsdsds': '', 'arg': '1'}, req.request
    else:
        assert req.request == {'dsdsds': b'', 'arg': '1'}, req.request
    assert req.files == {}, req.files


def test_worker_v1():
    socket_path = "tests/enp2"

    res = list()
    wsgi_res = {"body": list(),
                "status": None,
                "headers": None}
    err_res = list()

    http_res = {}

    def collector(func):
        def wrapper(environ, start_response):
            def g(func):
                def w(status, headers):
                    wsgi_res["status"] = status
                    wsgi_res["headers"] = headers
                    return func(status, headers)
                return w
            result = func(environ, g(start_response))
            wsgi_res["body"].extend(result)
            return res
        return wrapper

    def ping(request, response):
        res.append(1)
        inc = yield request.read()
        res.append(2)
        res.append(inc)
        with response:
            response.write("A")
            res.append(3)

    def bad_ping(request, response):
        raise Exception("Exception")

    def notclosed(request, response):
        yield request.read()
        response.write("A")

    @collector
    def wsgi_app(environ, start_response):
        response_body = 'Method %s' % environ['REQUEST_METHOD']
        status = '200 OK'
        response_headers = [('Content-Type', 'text/plain'),
                            ('Content-Length', str(len(response_body)))]
        start_response(status, response_headers)
        return [response_body, "A"]

    @http
    def http_test(request, response):
        req = yield request.read()
        http_res["req"] = req
        response.write_head(200, {'Content-Type': 'text/plain'})
        response.write("OK")
        response.close()

    def error_handler(request, response):
        try:
            yield request.read()
        except Exception as err:
            err_res.append(err)

    kwargs = dict(app="testapp",
                  endpoint=socket_path,
                  uuid="randomuuid",
                  disown_timeout=1,
                  heartbeat_timeout=2)

    main_v1(socket_path, 10)
    w = WorkerV1(**kwargs)
    w.run({"ping": ping,
           "bad_ping": bad_ping,
           "notclosed": notclosed,
           "http_test": http_test,
           "err_res": error_handler,
           "http": wsgi(wsgi_app)})

    assert res[:4] == [1, 2, 'pong', 3], res[:4]
    assert wsgi_res["body"] == ["Method POST", "A"], wsgi_res
    assert wsgi_res["status"] == '200 OK', wsgi_res
    assert wsgi_res["headers"] == [('Content-Type', 'text/plain'), ('Content-Length', '11')], wsgi_res["headers"]

    req = http_res["req"]

    assert req.body == BODY, req.body
    assert req.headers == dict(HEADERS), req.headers
    assert req.meta["version"] == HTTP_VERSION, req.meta["version"]
    if sys.version_info[0] == 2:
        assert req.request == {'dsdsds': '', 'arg': '1'}, req.request
    else:
        assert req.request == {'dsdsds': b'', 'arg': '1'}, req.request
    assert req.files == {}, req.files

    assert len(err_res) == 1, err_res
    assert isinstance(err_res[0], RequestError)
    assert err_res[0].code == 100
    assert err_res[0].reason == "test_err"


def test_worker_unable_to_connect():
    socket_path = "tests/enp2"
    kwargs = dict(app="testapp",
                  endpoint=socket_path,
                  uuid="randomuuid",
                  disown_timeout=1,
                  heartbeat_timeout=2)
    w = Worker(**kwargs)
    w.run()
