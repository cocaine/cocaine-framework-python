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
from threading import Lock

from msgpack import unpackb

from cocaine.asio import message
from cocaine.asio.message import Message
from cocaine.exceptions import ServiceError
from cocaine.futures import Future
from cocaine.futures import chain
from cocaine.asio.baseservice import BaseService

__all__ = ["Service"]


class Service(BaseService):

    def __init__(self, name, endpoint="localhost", port=10053, init_args=sys.argv, **kwargs):
        super(Service, self).__init__(name, endpoint, port, init_args, **kwargs)

        self._subscribers = dict()
        self.lock = Lock()

        def closure(number):
            def wrapper(*args):
                if not self.connected:
                    raise ServiceError(self.servicename, "Service is disconnected", -200)
                future = Future()
                c = chain.Chain([lambda: future])
                with self.lock:
                    self._counter += 1
                    self.w_stream.write([number, self._counter, args])
                    self._subscribers[self._counter] = future
                return c
            return wrapper

        for number, methodname in self._service_api.iteritems():
            setattr(self, methodname, closure(number))

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
