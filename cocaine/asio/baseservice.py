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

from msgpack import Unpacker, packb, unpackb

from cocaine.asio import ev
from cocaine.asio.pipe import Pipe
from cocaine.asio.stream import ReadableStream
from cocaine.asio.stream import WritableStream
from cocaine.asio.stream import Decoder
from cocaine.asio import message
from cocaine.asio.message import Message
from cocaine.exceptions import ServiceError
from cocaine.exceptions import LocatorResolveError

from locator import Locator


class BaseService(object):
    """ Implements basic functional for services:
    * all asio stuff
    * perform_sync method for synchronous operations
    You should reimplement _on_message function - this is callback for decoder,
    so this function is called with every incoming decoded message
    """

    def __init__(self, name, endpoint="127.0.0.1", port=10053, init_args=sys.argv, **kwargs):
        """
        It:
        * goes to Locator and get service api (put into self._service_api)
        * initializes event loop and all asio elements (write/read streams)
        * initializes session counter
        * registers callback on epoll READ event and\
        binds callback to decoder (_on_message)
        """
        if '--locator' in init_args:
            try:
                port = int(init_args[init_args.index('--locator') + 1])
            except ValueError as err:
                port = 10053
            except IndexError as err:
                port = 10053
        
        self._try_reconnect = kwargs.get("reconnect_once", True)
        self._counter = 1
        self.loop = ev.Loop()

        self._locator_host = endpoint
        self._locator_port = port
        self.servicename = name

        self._init_endpoint() # initialize pipe

        self.decoder = Decoder()
        self.decoder.bind(self._on_message)

        self.w_stream = WritableStream(self.loop, self.pipe)
        self.r_stream = ReadableStream(self.loop, self.pipe)
        self.r_stream.bind(self.decoder.decode)

        self.loop.register_read_event(self.r_stream._on_event, self.pipe.fileno())

    def _init_endpoint(self):
        locator = Locator()
        self.service_endpoint, _, service_api = locator.resolve(self.servicename, self._locator_host, self._locator_port)
        self._service_api = service_api
        # msgpack convert in list or tuple depend on version - make it tuple
        self.pipe = Pipe(tuple(self.service_endpoint), self.reconnect if self._try_reconnect else None)
        self.loop.bind_on_fd(self.pipe.fileno())
        
    def reconnect(self):
        self.loop.stop_listening(self.pipe.fileno())
        #try:
        #    self.pipe.sock.close()
        #except Exception as err:
        #    print(str(err))
        try:
            self._init_endpoint()
        except LocatorResolveError as err:
            pass
        else:
            self.w_stream.reconnect(self.pipe)
            self.r_stream.reconnect(self.pipe)

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
            # DO IT SYNC
            self.pipe.settimeout(timeout)
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
        raise NotImplementedError()

    @property
    def connected(self):
        return self.pipe.connected
