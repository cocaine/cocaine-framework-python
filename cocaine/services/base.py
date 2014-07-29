#
#    Copyright (c) 2014+ Anton Tyurin <noxiouz@yandex.ru>
#    Copyright (c) 2014+ Evgeny Safronov <division494@gmail.com>
#    Copyright (c) 2011-2014 Other contributors as noted in the AUTHORS file.
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

from __future__ import with_statement
import itertools
import logging

try:
    import asyncio
except ImportError:
    import trollius as asyncio

import msgpack

from ..concurrent import Stream
from ..common import CocaineErrno
from ..asio.protocol import CocaineProtocol
from ..asio.rpc import API

log = logging.getLogger('cocaine.service')


class Tx(object):
    def __init__(self, dtree, io_layer, counter):
        self.api = dtree
        self._io_layer = io_layer
        self.counter = counter
        self.log = logging.LoggerAdapter(log, {'service': 'tx', 'id': id(self)})

    def __getattr__(self, name):
        self.log.debug("invoking generic method: '%s'", name)

        def on_getattr(*args):
            return self._invoke(name, *args)
        return on_getattr

    @asyncio.coroutine
    def _invoke(self, method_name, *args):
        yield self._io_layer.connect()
        for method_id, (method, tx_tree, rx_tree) in self.api.iteritems():
            if method == method_name:
                self.log.debug("method has been found %s", method_name)
                counter = self.counter
                self.log.debug('sending message: %s', [counter, method_id, args])
                self._io_layer.pr.write(msgpack.packb([counter, method_id, args]))
                raise asyncio.Return(None)

        raise AttributeError(method_name)


class BaseService(object):
    def __init__(self, name, host='localhost', port=10053, loop=None):
        self.loop = loop or asyncio.get_event_loop()
        self._state_lock = asyncio.Lock()
        self.host = host
        self.port = port
        self.name = name
        # Protocol
        self.pr = None
        # Should I add connection epoch?
        # Epoch is useful when on_failure is called
        self.sessions = {}
        self.counter = itertools.count(1)

        self.api = {}
        self._extra = {'service': self.name, 'id': id(self)}
        self.log = logging.LoggerAdapter(log, self._extra)

    def connected(self):
        return self.pr and self.pr.connected()

    @asyncio.coroutine
    def connect(self):
        log.debug("checking if service connected", extra=self._extra)
        # Double checked locking
        if self.connected():
            log.debug("already connected", extra=self._extra)
            return

        with (yield self._state_lock):
            if self.connected():
                log.debug("already connected", extra=self._extra)
                return

            log.debug("connecting ...", extra=self._extra)
            proto_factory = CocaineProtocol.factory(self.on_message, self.on_failure)
            _, self.pr = yield self.loop.create_connection(proto_factory, self.host, self.port)
            self.log.debug("successfully connected: %s", [self.host, self.port])

    def on_message(self, unpacked_data):
        session, msg_type, payload = unpacked_data
        self.log.debug("session %d, type %d, payload %s", session, msg_type, payload)
        stream = self.sessions.get(session)
        if stream is None:
            self.log.warning("Unknown session %d", session)
            return

        if stream.push(msg_type, payload):
            self.sessions.pop(session, None)

    def on_failure(self, exc):
        log.warn("service is disconnected: %s", exc, extra=self._extra)

        for stream in self.sessions.itervalues():
            stream.error(CocaineErrno.ESRVDISCON, "service %s is disconnected" % self.name)

    @asyncio.coroutine
    def _invoke(self, method_name, *args):
        yield self.connect()
        for method_id, (method, tx_tree, rx_tree) in self.api.iteritems():
            if method == method_name:
                self.log.debug("method has been found %s", method_name)
                counter = self.counter.next()
                self.log.debug('sending message: %s', [counter, method_id, args])
                self.pr.write(msgpack.packb([counter, method_id, args]))

                self.log.debug("RX TREE %s", rx_tree)
                self.log.debug("TX TREE %s", tx_tree)
                rx = Stream(rx_tree)
                tx = Tx(tx_tree, self, counter)
                self.sessions[counter] = rx
                raise asyncio.Return((rx, tx))

        raise AttributeError(method_name)

    def __getattr__(self, name):
        self.log.debug("invoking generic method: '%s'", name)

        def on_getattr(*args):
            return self._invoke(name, *args)
        return on_getattr


class Locator(BaseService):
    def __init__(self, host="localhost", port=10053, loop=None):
        super(Locator, self).__init__(name="locator", host=host, port=port, loop=loop)
        self.api = API.Locator


class Service(BaseService):
    def __init__(self, name, host="localhost", port=10053, version=0, loop=None):
        super(Service, self).__init__(name=name, loop=loop)
        self.locator = Locator(host=host, port=port, loop=loop)
        self.api = {}
        self.host = None
        self.port = None
        self.version = version

    @asyncio.coroutine
    def connect(self):
        log.debug("checking if service connected", extra=self._extra)
        if self.connected():
            log.debug("already connected", extra=self._extra)
            return

        log.info("resolving ...", extra=self._extra)
        rx, _ = yield self.locator.resolve(self.name)
        (self.host, self.port), version, self.api = yield rx.get()
        log.info("successfully resolved", extra=self._extra)

        # Version compatibility should be checked here.
        if not (self.version == 0 or version == self.version):
            raise Exception("wrong service `%s` API version %d, %d is needed" %
                            (self.name, version, self.version))
        yield super(Service, self).connect()
