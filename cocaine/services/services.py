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
from threading import Lock

from msgpack import Unpacker, packb, unpackb

from cocaine.asio import ev
from cocaine.asio.pipe import ServicePipe
from cocaine.asio.stream import ReadableStream
from cocaine.asio.stream import WritableStream
from cocaine.asio.stream import Decoder
from cocaine.asio import message
from cocaine.asio.message import Message
from cocaine.exceptions import ServiceError
from locator import Locator
from cocaine.futures import Future


__all__ = ["Service"]


class Service(object):

    def __init__(self, name, endpoint="localhost", port=10053, init_args=sys.argv):

        self.lock = Lock()
        def closure(number):
            def wrapper(*args):
                future = Future()
                with self.lock:
                    self._counter += 1
                    self.w_stream.write([number, self._counter, args])
                    self._subscribers[self._counter] = future
                return future
            return wrapper

        if '--locator' in init_args:
            try:
                port = int(init_args[init_args.index('--locator') + 1])
            except ValueError as err:
                port = 10053
            except IndexError as err:
                port = 10053


        locator = Locator()
        service_endpoint, _, service_api = locator.resolve(name, endpoint, port)

        self._service_api = service_api
        self.servicename = name

        for number, methodname in service_api.iteritems():
            setattr(self, methodname, closure(number))

        self.loop = ev.Loop()

        self._counter = 1
        self._subscribers = dict()
        
        # msgpack convert in list or tuple depend on version - make it tuple
        self.pipe = ServicePipe(tuple(service_endpoint))

        self.decoder = Decoder()
        self.decoder.bind(self._on_message)

        self.loop.bind_on_fd(self.pipe.fileno())

        self.w_stream = WritableStream(self.loop, self.pipe)
        self.r_stream = ReadableStream(self.loop, self.pipe)
        self.r_stream.bind(self.decoder.decode)

        self.loop.register_read_event(self.r_stream._on_event, self.pipe.fileno())
        try:
            self.app_name = init_args[init_args.index("--app") + 1]
        except ValueError:
            self.app_name = "standalone"

    def perform_sync(self, method, *args, **kwargs):
        """ Do not use the service synchronously after treatment to him asynchronously!
        Use for these purposes the other instance of the service!
        """

        timeout = kwargs.get("timeout", 5)

        # Get number of current method
        try:
            number = (_num for _num, _name in self._service_api.iteritems() if _name == method).next()
        except StopIteration as err:
            raise ServiceError(self.servicename, "method %s is not available" % method, -100)

        try:
            self.pipe.settimeout(timeout) # DO IT SYNC
            self.pipe.writeall(packb([number, self._counter, args]))
            self._counter += 1
            u = Unpacker()
            msg = None

            # If we receive rpc::error, put ServiceError here, 
            # and raise this error instead of StopIteration on rpc::choke,
            # because after rpc::error we always receive choke.
            _error = None

            while True:
                response = self.pipe.recv(4096)
                u.feed(response)
                for _data in u:
                    msg = Message.initialize(_data)
                    if msg is None:
                        continue
                    if msg.id == message.RPC_CHUNK:
                        yield unpackb(msg.data)
                    elif msg.id == message.RPC_CHOKE:
                        raise _error or StopIteration
                    elif msg.id == message.RPC_ERROR:
                        _error = ServiceError(self.servicename, msg.message, msg.code)
        finally:
            self.pipe.settimeout(0)  # return to non-blocking mode

    def _on_message(self, args):
        msg = Message.initialize(args)
        if msg is None:
            return
        try:
            if msg.id == message.RPC_CHUNK:
                self._subscribers[msg.session].callback(unpackb(msg.data))
            elif msg.id == message.RPC_CHOKE:
                future = self._subscribers.pop(msg.session, None)
                if future is not None:
                    future.close()
            elif msg.id == message.RPC_ERROR:
                self._subscribers[msg.session].error(ServiceError(self.servicename, msg.message, msg.code))
        except Exception as err:
            print "Exception in _on_message: %s" % str(err)
