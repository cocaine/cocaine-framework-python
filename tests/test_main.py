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

from tornado.ioloop import IOLoop

from cocaine.detail.service import InvalidApiVersion
from cocaine.detail.service import Rx, Tx
from cocaine.detail.service import BaseService
from cocaine.detail.service import ServiceError, ChokeEvent, InvalidMessageType
from cocaine.exceptions import ConnectionError, DisconnectionError
from cocaine.worker.request import Stream

from cocaine.services import Locator
from cocaine.services import Service

import msgpack
from nose import tools


@tools.raises(AttributeError)
def test_service_attribute_error():
    io = IOLoop.current()
    locator = Locator("localhost", 10053, loop=io)
    locator.random_attribute().get()


def test_locator():
    io = IOLoop.current()
    locator = Locator("localhost", 10053, loop=io)
    chan = io.run_sync(lambda: locator.resolve("storage"))
    endpoint, version, api = io.run_sync(chan.rx.get, timeout=4)
    assert version == 1, "invalid version number %s" % version
    assert isinstance(endpoint, (list, tuple)), "invalid endpoint type %s" % type(endpoint)
    assert isinstance(api, dict)


def test_service_with_seed():
    io = IOLoop.current()
    n1 = Service("node", seed="TEST_SEED")
    channel = io.run_sync(n1.list)
    app_list = io.run_sync(channel.rx.get)
    assert isinstance(app_list, list)


def test_on_close():
    io = IOLoop.current()
    locator = Locator("localhost", 10053, loop=io)
    locator.disconnect()

    locator = Locator("localhost", 10053, loop=io)
    io.run_sync(locator.connect)
    io.run_sync(locator.connect)
    locator.disconnect()


def test_service_double_connect():
    io = IOLoop.current()
    node = Service("node", host="localhost", port=10053, loop=io)
    io.run_sync(node.connect)
    io.run_sync(node.connect)


@tools.raises(Exception)
def test_service_connection_failure():
    io = IOLoop.current()
    s = BaseService(name="dummy", host="localhost", port=43000, loop=io)
    s.endpoints.append(("localhost", 43001))
    io.run_sync(s.connect)


@tools.raises(InvalidApiVersion)
def test_service_invalid_api_version():
    io = IOLoop.current()
    node = Service("node", host="localhost", port=10053, version=100, loop=io)
    io.run_sync(node.connect)


def test_node_service():
    io = IOLoop.current()
    node = Service("node", host="localhost", port=10053, loop=io)
    channel = io.run_sync(node.list)
    app_list = io.run_sync(channel.rx.get)
    assert isinstance(app_list, list), "invalid app_list type `%s` %s " % (type(app_list), app_list)


@tools.raises(DisconnectionError)
def test_node_service_disconnection():
    io = IOLoop.current()
    node = Service("node", host="localhost", port=10053, loop=io)
    channel = io.run_sync(node.list)
    node.disconnect()
    # proper answer
    io.run_sync(channel.rx.get)
    # empty response
    io.run_sync(channel.rx.get)
    # disconnection error
    io.run_sync(channel.rx.get)


def test_node_service_bad_on_read():
    io = IOLoop.current()
    node = Service("node", host="localhost", port=10053, loop=io)
    malformed_message = msgpack.packb([-999, 0])
    node.on_read(malformed_message)
    message = msgpack.packb([-999, 0, []])
    node.on_read(message)


class TestRx(object):
    rx_tree = {0: ['write', None],
               1: ['error', {}],
               2: ['close', {}]}
    io = IOLoop.current()

    @tools.raises(ServiceError)
    def test_rx_error_branch(self):
        rx = Rx(self.rx_tree)
        rx.push(1, [-199, "dummy_error"])
        self.io.run_sync(rx.get)

    @tools.raises(ChokeEvent)
    def test_rx_done(self):
        rx = Rx(self.rx_tree)
        rx.push(2, [])
        self.io.run_sync(rx.get)
        self.io.run_sync(rx.get)

    @tools.raises(ChokeEvent)
    def test_rx_done_empty_queue(self):
        rx = Rx(self.rx_tree)
        rx.push(1, [-199, "DUMMY"])
        try:
            self.io.run_sync(rx.get)
        except Exception:
            pass
        self.io.run_sync(rx.get)

    @tools.raises(InvalidMessageType)
    def test_rx_unexpected_msg_type(self):
        io = IOLoop.current()
        rx = Rx(self.rx_tree)
        rx.push(4, [])
        io.run_sync(rx.get)


class TestTx(object):
    tx_tree = {0: ['dummy', None]}

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
        io = IOLoop.current()
        node = Service("node", host="localhost", port=10053, loop=io)
        channel = yield node.list()
        app_list = yield channel.rx.get()
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


@tools.raises(ServiceError)
def test_stream():
    io = IOLoop.current()
    stream = Stream()
    stream.error(100, "TESTERROR")
    io.run_sync(stream.get)
