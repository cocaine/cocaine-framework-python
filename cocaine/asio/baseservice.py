#
#    Copyright (c) 2011-2013 Anton Tyurin <noxiouz@yandex.ru>
#    Copyright (c) 2011-2013 Other contributors as noted in the AUTHORS file.
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

import sys
import time

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
    """
    Implements basic functional for services.

    * all asio stuff
    * perform_sync method for synchronous operations

    It:
    * goes to Locator and get service api (put into self._service_api)
    * initializes event loop and all asio elements (write/read streams)
    * initializes session counter
    * registers callback on epoll READ event
    and binds callback to decoder (_on_message)

    You should reimplement _on_message function - this is callback for decoder,
    so this function is called with every
    incoming decoded message.
    """

    def __init__(self, name, endpoint="127.0.0.1", port=10053, init_args=sys.argv, **kwargs):
        if '--locator' in init_args:
            try:
                port = int(init_args[init_args.index('--locator') + 1])
            except (ValueError, IndexError):
                port = 10053
        
        self._try_reconnect = kwargs.get("reconnect_once", True)
        self._counter = 1
        self.loop = ev.Loop()
        self.pipe = None

        self._locator_host = endpoint
        self._locator_port = port
        self.servicename = name
        self._service_api = None

        self._init_endpoint()  # initialize pipe

        self.decoder = Decoder()
        self.decoder.bind(self._on_message)

        self.w_stream = WritableStream(self.loop, self.pipe)
        self.r_stream = ReadableStream(self.loop, self.pipe)
        self.r_stream.bind(self.decoder.decode)

        self.loop.register_read_event(self.r_stream._on_event, self.pipe.fileno())

        self._reconnecting = False

    def _init_endpoint(self):
        locator = Locator()
        self.service_endpoint, _, service_api = locator.resolve(self.servicename,
                                                                self._locator_host,
                                                                self._locator_port)
        self._service_api = service_api
        # msgpack convert in list or tuple depend on version - make it tuple
        self.pipe = Pipe(tuple(self.service_endpoint),
                         self.reconnect if self._try_reconnect else None)
        self.pipe.connect()
        self.loop.bind_on_fd(self.pipe.fileno())
        
    def reconnect(self):
        if self.pipe.is_valid_fd:
            self.loop.stop_listening(self.pipe.fileno())
        try:
            self._init_endpoint()
        except LocatorResolveError:
            pass
        else:
            self.w_stream.reconnect(self.pipe)
            self.r_stream.reconnect(self.pipe)

    def async_reconnect(self, callback, timeout):
        if self._reconnecting:
            result = AsyncReconnectionResult()
            result.set_error(Exception("Already"))
            callback(result)
            return

        limit = time.time() + timeout
        if self.pipe.is_valid_fd:
            self.loop.stop_listening(self.pipe.fileno())
            self.pipe.close()
        self._reconnecting = True

        def on_locator_resolve(res):
            def on_connect(res):
                result = AsyncReconnectionResult()
                self._reconnecting = False
                try:
                    self.loop.bind_on_fd(self.pipe.fileno())
                    self.w_stream.reconnect(self.pipe)
                    self.r_stream.reconnect(self.pipe)
                    result.set_res(res.get())
                except Exception as err:
                    result.set_error(err)
                finally:
                    callback(result)

            try:
                self.service_endpoint, _, service_api = res.get()
            except Exception as err:
                result = AsyncReconnectionResult()
                self._reconnecting = False
                result.set_error(err)
                callback(result)
            else:
                self.pipe = Pipe(tuple(self.service_endpoint), None)
                self.pipe.async_connect(on_connect, limit - time.time())

        locator = Locator()
        locator.async_resolve(self.servicename,
                              self._locator_host,
                              self._locator_port, on_locator_resolve, timeout)

    def perform_sync(self, method, *args, **kwargs):
        """
        Performs synchronous chunk retrieving

        Warning: Do not use the service synchronously after treatment to him
        asynchronously!
        Use for these purposes the other instance of the service!
        """

        timeout = kwargs.get("timeout", 5)

        # Get number of current method
        try:
            number = (_num for _num, _name in self._service_api.iteritems()
                      if _name == method).next()
        except StopIteration:
            raise ServiceError(self.servicename, "method %s is not available" % method, -100)

        try:
            # DO IT SYNC
            self.pipe.settimeout(timeout)
            self.pipe.writeall(packb([number, self._counter, args]))
            self._counter += 1
            u = Unpacker()

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
                        _error = ServiceError(self.servicename,
                                              msg.message,
                                              msg.code)
        finally:
            self.pipe.settimeout(0)  # return to non-blocking mode

    def _on_message(self, args):
        raise NotImplementedError()

    @property
    def connected(self):
        if not self.pipe.is_valid_fd:
            return False

        if self.pipe is not None:
            return self.pipe.connected
        else:
            return False

    def __del__(self):
        if self.pipe is not None and self.pipe.is_valid_fd:
            self.loop.stop_listening(self.pipe.fileno())
            self.pipe.close()


class AsyncReconnectionResult(object):
    def set_error(self, err):
        def res():
            raise err
        setattr(self, "get", res)

    def set_res(self, res):
        setattr(self, "get", lambda: res)
