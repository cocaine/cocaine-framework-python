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

import socket

from concurrent.futures import Future

from cocaine.detail.service import CocaineIO
from cocaine.detail.service import CocaineTCPClient
from cocaine.detail.service import InvalidApiVersion
from cocaine.detail.service import Rx, Tx
from cocaine.detail.service import BaseService
from cocaine.detail.service import ServiceError, ChokeEvent, InvalidMessageType
from cocaine.exceptions import ConnectionError, DisconnectionError

from cocaine.services import Locator
from cocaine.services import Service

import msgpack
from nose import tools


@tools.raises(AttributeError)
def test_loop():
    io = CocaineIO.instance()
    io.UNEXISTED_ATTRIBUTE


def test_add_future():
    expected_res = "EXPECTED"
    io = CocaineIO.instance()
    f = Future()
    io.post(f.set_result, expected_res)
    res = f.result(timeout=4)
    assert res == expected_res


def test_connect():
    io = CocaineIO.instance()
    client = CocaineTCPClient(io_loop=io)
    try:
        client.connect("localhost", 10053).wait(2)
    finally:
        client.close()


@tools.raises(IOError)
def test_failed_connect():
    io = CocaineIO.instance()
    client = CocaineTCPClient(io_loop=io)
    client.connect("localhost2", 10053).wait(4)


@tools.raises(AttributeError)
def test_service_attribute_error():
    io = CocaineIO.instance()
    locator = Locator("localhost", 10053, loop=io)
    locator.random_attribute().get()


def test_locator():
    io = CocaineIO.instance()
    locator = Locator("localhost", 10053, loop=io)
    chan = locator.resolve("storage").wait(4)
    endpoint, version, api = chan.rx.get().wait(1)
    assert version == 1, "invalid version number %s" % version
    assert isinstance(endpoint, (list, tuple)), "invalid endpoint type %s" % type(endpoint)
    assert isinstance(api, dict)


def test_on_close():
    io = CocaineIO.instance()
    locator = Locator("localhost", 10053, loop=io)
    locator.disconnect()

    locator = Locator("localhost", 10053, loop=io)
    locator.connect().wait(4)
    locator.connect().wait(4)
    locator.disconnect()


def test_service_double_connect():
    io = CocaineIO.instance()
    node = Service("node", host="localhost", port=10053, loop=io)
    node.connect().wait(4)
    node.connect().wait(4)


@tools.raises(Exception)
def test_service_connection_failure():
    io = CocaineIO.instance()
    s = BaseService(name="dummy", host="localhost", port=43000, loop=io)
    s.endpoints.append(("localhost", 43001))
    s.connect().wait(3)


@tools.raises(InvalidApiVersion)
def test_service_invalid_api_version():
    io = CocaineIO.instance()
    node = Service("node", host="localhost", port=10053, version=100, loop=io)
    node.connect().wait(4)


def test_node_service():
    io = CocaineIO.instance()
    node = Service("node", host="localhost", port=10053, loop=io)
    channel = node.list().wait(1)
    app_list = channel.rx.get().wait(1)
    assert isinstance(app_list, list), "invalid app_list type `%s` %s " % (type(app_list), app_list)


@tools.raises(DisconnectionError)
def test_node_service_disconnection():
    io = CocaineIO.instance()
    node = Service("node", host="localhost", port=10053, loop=io)
    channel = node.list().wait(1)
    node.disconnect()
    # proper answer
    channel.rx.get().wait(1)
    # empty response
    channel.rx.get().wait(1)
    # disconnection error
    channel.rx.get().wait(1)


def test_node_service_bad_on_read():
    io = CocaineIO.instance()
    node = Service("node", host="localhost", port=10053, loop=io)
    malformed_message = msgpack.packb([-999, 0])
    node.on_read(malformed_message)
    message = msgpack.packb([-999, 0, []])
    node.on_read(message)


class TestRx(object):
    rx_tree = {0: ['write', None],
               1: ['error', {}],
               2: ['close', {}]}

    @tools.raises(ServiceError)
    def test_rx_error_branch(self):
        rx = Rx(self.rx_tree)
        rx.push(1, [-199, "dummy_error"])
        rx.get().wait(4)

    @tools.raises(ChokeEvent)
    def test_rx_done(self):
        rx = Rx(self.rx_tree)
        rx.push(2, [])
        rx.get().wait(1)
        rx.get().wait(1)

    @tools.raises(ChokeEvent)
    def test_rx_done_empty_queue(self):
        rx = Rx(self.rx_tree)
        rx.push(1, [-199, "DUMMY"])
        try:
            rx.get().wait(4)
        except Exception:
            pass
        rx.get().wait(4)

    @tools.raises(InvalidMessageType)
    def test_rx_unexpected_msg_type(self):
        rx = Rx(self.rx_tree)
        rx.push(4, [])
        rx.get().wait(4)


class TestTx(object):
    tx_tree = {0: ['dummy', None, {}]}

    class PipeMock(object):
        def write(self, *args):
            pass

    @tools.raises(AttributeError)
    def test_tx(self):
        tx = Tx(self.tx_tree, self.PipeMock(), 1)
        tx.dummy().wait(4)
        tx.failed().wait(4)


def test_current_ioloop():
    from tornado import gen
    from tornado.ioloop import IOLoop

    @gen.coroutine
    def f():
        io = CocaineIO.instance()
        node = Service("node", host="localhost", port=10053, loop=io)
        channel = yield node.list()
        app_list = channel.rx.get().wait()
        assert isinstance(app_list, list)

    io_l = IOLoop.current()
    io_l.run_sync(f, timeout=2)

    io_l.add_future(f(), lambda x: io_l.stop())
    io_l.start()


def test_connection_error():
    resolve_info = socket.getaddrinfo("localhost", 10053)
    for item in resolve_info:
        ConnectionError(item[-1], "Test")
    ConnectionError("UnixDomainSocket", "Test")
