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


class _BaseService(object):

    def __init__(self, endpoint):
        self.m_service = ev.Service()
        self.m_pipe = ServicePipe(endpoint)
        self.m_app_name = sys.argv[sys.argv.index("--app") + 1]

        self.m_decoder = Decoder()
        self.m_decoder.bind(self.on_message)

        self.m_service.bind_on_fd(self.m_pipe.fileno())

        self.m_w_stream = WritableStream(self.m_service, self.m_pipe)
        self.m_r_stream = ReadableStream(self.m_service, self.m_pipe)
        self.m_r_stream.bind(self.m_decoder.decode)

        self.m_service.register_read_event(self.m_r_stream._on_event, self.m_pipe.fileno())

    def on_message(self, *args):
        pass


class Service(object):

    def __init__(self, name, endpoint="localhost", port=10053):
        def closure(number):
            def wrapper(*args):
                def register_callback(clbk):
                    self.m_w_stream.write([number, self._counter, args])
                    self._subscribers[self._counter] = clbk
                    self._counter += 1
                return register_callback
            return wrapper

        service_endpoint, _, service_api = self._get_api(name, endpoint, port)

        for number, name in service_api.iteritems():
            setattr(self, name, closure(number))

        self.m_service = ev.Service()

        self._counter = 1
        self._subscribers = dict()

        self.m_pipe = ServicePipe((service_endpoint.split(':')[0], int(service_endpoint.split(':')[1])))

        self.m_decoder = Decoder()
        self.m_decoder.bind(self._on_message)

        self.m_service.bind_on_fd(self.m_pipe.fileno())

        self.m_w_stream = WritableStream(self.m_service, self.m_pipe)
        self.m_r_stream = ReadableStream(self.m_service, self.m_pipe)
        self.m_r_stream.bind(self.m_decoder.decode)

        self.m_service.register_read_event(self.m_r_stream._on_event, self.m_pipe.fileno())
        self.m_app_name = sys.argv[sys.argv.index("--app") + 1]

    def _get_api(self, name, endpoint, port):
        locator_pipe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        locator_pipe.settimeout(4.0)
        locator_pipe.connect((endpoint, port))
        locator_pipe.send(packb([0, 1, [name]]))
        u = Unpacker()
        is_received = False
        while not is_received:
            response = locator_pipe.recv(80960)
            u.feed(response)
            msg = Message.initialize(u.next())

            if msg is not None:
                is_received = True
        locator_pipe.close()
        if msg.id == PROTOCOL_LIST.index("rpc::chunk"):
            return unpackb(msg.data)
        if msg.id == PROTOCOL_LIST.index("rpc::error"):
            raise Exception("No service error")


    def _on_message(self, args):
        msg = Message.initialize(args)
        if msg is None:
            print "Drop invalid message"
            return
        if msg.id == PROTOCOL_LIST.index("rpc::chunk"):
            self._subscribers[msg.session](msg.data)
        elif msg.id == PROTOCOL_LIST.index("rpc::choke"):
            self._subscribers.pop(msg.session, None)
        elif msg.id == PROTOCOL_LIST.index("rpc::error"):
            print msg.message
