# encoding: utf-8
#
#    Copyright (c) 2011-2013 Anton Tyurin <noxiouz@yandex.ru>
#    Copyright (c) 2011-2013 Other contributors as noted in the AUTHORS file.
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

import sys
import errno
import socket
import weakref

from msgpack import Unpacker, packb, unpackb

from cocaine.asio import ev
from cocaine.asio.pipe import ServicePipe
from cocaine.asio.stream import ReadableStream
from cocaine.asio.stream import WritableStream
from cocaine.asio.stream import Decoder
from cocaine.asio.message import PROTOCOL_LIST
from cocaine.asio.message import Message
from cocaine.exceptions import ServiceError


class _BaseService(object):

    def __init__(self, endpoint):
        self.service = ev.Service()
        self.pipe = ServicePipe(endpoint)
        self.app_name = sys.argv[sys.argv.index("--app") + 1]

        self.decoder = Decoder()
        self.decoder.bind(self.on_message)

        self.service.bind_on_fd(self.pipe.fileno())

        self.w_stream = WritableStream(self.service, self.pipe)
        self.r_stream = ReadableStream(self.service, self.pipe)
        self.r_stream.bind(self.decoder.decode)

        self.service.register_read_event(self.r_stream._on_event, self.pipe.fileno())

    def on_message(self, *args):
        pass


class Service(object):

    def __init__(self, name, endpoint="localhost", port=10053):
        def closure(number):
            def wrapper(*args):
                def register_callback(callback, errorback=None):
                    self.w_stream.write([number, self._counter, args])
                    self._subscribers[self._counter] = (callback, errorback)
                    # FIX: Move counter increment for supporting stream-loke services
                    self._counter += 1
                return register_callback
            return wrapper

        service_endpoint, _, service_api = self._get_api(name, endpoint, port)

        self._service_api = service_api
        self.servicename = name

        for number, methodname in service_api.iteritems():
            setattr(self, methodname, closure(number))

        self.service = ev.Service()

        self._counter = 1
        self._subscribers = dict()

        self.pipe = ServicePipe((service_endpoint.split(':')[0], int(service_endpoint.split(':')[1])))

        self.decoder = Decoder()
        self.decoder.bind(self._on_message)

        self.service.bind_on_fd(self.pipe.fileno())

        self.w_stream = WritableStream(self.service, self.pipe)
        self.r_stream = ReadableStream(self.service, self.pipe)
        self.r_stream.bind(self.decoder.decode)

        self.service.register_read_event(self.r_stream._on_event, self.pipe.fileno())
        self.app_name = sys.argv[sys.argv.index("--app") + 1]

    def _get_api(self, name, endpoint, port):
        locator_pipe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        locator_pipe.settimeout(4.0)
        locator_pipe.connect((endpoint, port))
        locator_pipe.send(packb([0, 1, [name]]))
        u = Unpacker()
        msg = None
        while msg is None:
            response = locator_pipe.recv(80960)
            u.feed(response)
            msg = Message.initialize(u.next())

        locator_pipe.close()
        if msg.id == PROTOCOL_LIST.index("rpc::chunk"):
            return unpackb(msg.data)
        if msg.id == PROTOCOL_LIST.index("rpc::error"):
            raise Exception(msg.message)

    def perform_sync(self, method, *args):
        number = (_num for _num, _name in self._service_api.iteritems() if _name == method).next()
        self.pipe.write(packb([number, 1, args]))
        u = Unpacker()
        msg = None
        try:
            self.pipe.settimeout(1.0) # DO IT SYNC
            while msg is None:
                response = self.pipe.recv(80960)
                u.feed(response)
                msg = Message.initialize(u.next())
        finally:
            self.pipe.settimeout(0) #return to non-blocking mode
        if msg.id == PROTOCOL_LIST.index("rpc::chunk"):
            return unpackb(msg.data)
        elif msg.id == PROTOCOL_LIST.index("rpc::error"):
            raise Exception(msg.message)

    def _on_message(self, args):
        msg = Message.initialize(args)
        if msg is None:
            print "Drop invalid message"
            return
        try:
            if msg.id == PROTOCOL_LIST.index("rpc::chunk"):
                self._subscribers[msg.session][0](msg.data)
            elif msg.id == PROTOCOL_LIST.index("rpc::choke"):
                self._subscribers.pop(msg.session, None)
            elif msg.id == PROTOCOL_LIST.index("rpc::error"):
                self._subscribers[msg.session][1](ServiceError(self.servicename, msg.message, msg.code))
        except Exception as err:
            print "Exception in _on_message: %s" % str(err)
