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
import socket

from tornado import gen
from tornado.ioloop import IOLoop

from cocaine.detail.service import InvalidApiVersion
from cocaine.detail.baseservice import BaseService
from cocaine.detail.channel import primitive_protocol, streaming_protocol, null_protocol
from cocaine.detail.channel import ProtocolError
from cocaine.detail.channel import Rx, Tx
from cocaine.exceptions import ChokeEvent
from cocaine.exceptions import ConnectionError
from cocaine.exceptions import InvalidMessageType
from cocaine.exceptions import ServiceError
from cocaine.worker.request import Stream, RequestError

from cocaine.services import Locator
from cocaine.services import Service

import msgpack
from nose import tools

log = logging.getLogger()
log.setLevel(logging.DEBUG)


@tools.raises(AttributeError)
def test_service_attribute_error():
    io = IOLoop.current()
    locator = Locator([("localhost", 10053)], io_loop=io)
    locator.random_attribute().get()


def test_locator():
    io = IOLoop.current()
    locator = Locator(endpoints=[["localhost", 10053]], io_loop=io)
    chan = io.run_sync(lambda: locator.resolve("storage"))
    endpoint, version, api = io.run_sync(chan.rx.get, timeout=4)
    assert version == 1, "invalid version number %s" % version
    assert isinstance(endpoint, (list, tuple)), "invalid endpoint type %s" % type(endpoint)
    assert isinstance(api, dict)


def test_service_with_seed():
    io = IOLoop.current()
    n1 = Service("storage", seed="TEST_SEED")
    channel = io.run_sync(lambda: n1.find('app', ['apps']))
    app_list = io.run_sync(channel.rx.get)
    assert isinstance(app_list, list)


def test_on_close():
    io = IOLoop.current()
    locator = Locator(endpoints=[["localhost", 10053]], io_loop=io)
    locator.disconnect()

    locator = Locator(endpoints=[["localhost", 10053]], io_loop=io)
    io.run_sync(locator.connect)
    io.run_sync(locator.connect)
    locator.disconnect()


def test_service_double_connect():
    io = IOLoop.current()
    storage = Service("storage", endpoints=[["localhost", 10053]], io_loop=io)
    io.run_sync(lambda: storage.connect("TRACEID"))
    io.run_sync(storage.connect)


@tools.raises(Exception)
def test_service_connection_failure():
    io = IOLoop.current()
    s = BaseService(name="dummy", endpoints=[["localhost", 43000]], io_loop=io)
    s.endpoints.append(("localhost", 43001))
    io.run_sync(s.connect)


@tools.raises(InvalidApiVersion)
def test_service_invalid_api_version():
    io = IOLoop.current()
    storage = Service("storage", endpoints=[["localhost", 10053]], version=100, io_loop=io)
    io.run_sync(storage.connect)


def test_storage_service():
    io = IOLoop.current()

    @gen.coroutine
    def main():
        storage = Service("storage", endpoints=[["localhost", 10053]], io_loop=io)
        channel = yield storage.find('app', ['apps'])
        res = yield channel.rx.get()
        raise gen.Return(res)

    app_list = io.run_sync(main, timeout=10)
    assert isinstance(app_list, list), "invalid app_list type `%s` %s " % (type(app_list), app_list)


def test_node_service_bad_on_read():
    io = IOLoop.current()
    node = Service("node", endpoints=[["localhost", 10053]], io_loop=io)
    malformed_message = msgpack.packb([-999, 0])
    node.on_read(malformed_message)
    message = msgpack.packb([-999, 0, []])
    node.on_read(message)


class TestRx(object):
    rx_tree = {0: ['write', None],
               1: ['error', {}],
               2: ['close', {}]}
    io = IOLoop.current()

    def test_print(self):
        log.info(Rx(self.rx_tree))

    @tools.raises(ServiceError)
    def test_rx_error_branch(self):
        rx = Rx(self.rx_tree)
        rx.push(1, [(-199, 42), "dummy_error"])
        self.io.run_sync(rx.get)

    @tools.raises(ChokeEvent)
    def test_rx_done(self):
        rx = Rx(self.rx_tree)
        rx.push(2, [])
        self.io.run_sync(lambda: rx.get(timeout=1))
        self.io.run_sync(rx.get)

    @tools.raises(ChokeEvent)
    def test_rx_done_empty_queue(self):
        rx = Rx(self.rx_tree)
        rx.push(1, [(-199, 32), "DUMMY"])
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

    @tools.raises(ChokeEvent)
    def test_rx_on_done(self):
        io = IOLoop.current()
        rx = Rx(self.rx_tree)
        rx.done()
        io.run_sync(rx.get)


class TestTx(object):
    tx_tree = {0: ['dummy', None]}

    class PipeMock(object):
        def write(self, *args):
            pass

    def test_print(self):
        log.info(Tx(self.tx_tree, self.PipeMock(), 1))

    @tools.raises(AttributeError)
    def test_tx(self):
        tx = Tx(self.tx_tree, self.PipeMock(), 1)
        tx.dummy().wait(4)
        tx.failed().wait(4)

    @tools.raises(ChokeEvent)
    def test_tx_on_done(self):
        io = IOLoop.current()
        tx = Tx(self.tx_tree, self.PipeMock(), 1)
        tx.done()
        io.run_sync(tx.get)


def test_current_ioloop():
    from tornado.ioloop import IOLoop

    @gen.coroutine
    def f():
        io = IOLoop.current()
        storage = Service("storage", endpoints=[["localhost", 10053]], io_loop=io)
        channel = yield storage.find('app', ['apps'])
        app_list = yield channel.rx.get()
        assert isinstance(app_list, list)
        raise gen.Return("OK")

    io_l = IOLoop.current()
    io_l.run_sync(f, timeout=2)

    io_l.add_future(f(), lambda x: io_l.stop())
    io_l.start()


def test_connection_error():
    resolve_info = socket.getaddrinfo("localhost", 10053)
    for item in resolve_info:
        ConnectionError(item[-1], "Test")
    ConnectionError("UnixDomainSocket", "Test")


@tools.raises(RequestError)
def test_stream():
    io = IOLoop.current()
    stream = Stream(io_loop=io)
    stream.error((0, 100), "TESTERROR")
    io.run_sync(stream.get)


@tools.raises(gen.TimeoutError)
def test_stream_timeout():
    io = IOLoop.current()
    stream = Stream(io_loop=io)
    io.run_sync(lambda: stream.get(timeout=0.5))


def test_primitive_protocol():
    assert null_protocol("A", 1) == ("A", 1)
    primitive_single_payload = ["A"]
    primitive = primitive_protocol("value", primitive_single_payload)
    assert primitive == primitive_single_payload[0], primitive
    primitive_sequence_payload = ["A", "B", "C"]
    primitive = primitive_protocol("value", primitive_sequence_payload)
    assert primitive == primitive_sequence_payload, primitive
    primitive_error = primitive_protocol("error", [(100, 100), "errormsg"])
    assert isinstance(primitive_error, ProtocolError), primitive_error


def test_streaming_protocol():
    streaming_single_payload = ["A"]
    streaming = streaming_protocol("write", streaming_single_payload)
    assert streaming == streaming_single_payload[0], streaming
    streaming_sequence_payload = ["A", "B", "C"]
    streaming = streaming_protocol("write", streaming_sequence_payload)
    assert streaming == streaming_sequence_payload, streaming
    streaming_error = streaming_protocol("error", [(100, 100)])  # error msg is optional
    assert isinstance(streaming_error, ProtocolError), streaming_error
