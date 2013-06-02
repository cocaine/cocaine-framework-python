#
#   Copyright (c) 2011-2013 Anton Tyurin <noxiouz@yandex.ru>
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

import socket
import time
import heapq
from threading import Lock

import msgpack

from cocaine.asio.message import Message
from cocaine.asio import message
from cocaine.exceptions import LocatorResolveError

class Cache(object):

    lock = Lock()

    def __init__(self, capacity=100):
        self._data = dict()
        self._heap = list()
        self._capacity = capacity if capacity > 1 else 1
        self._cache_lifetime = 10

    def set_cache_lifetime(self, time_in_sec):
        with self.lock:
            self._cache_lifetime = time_in_sec

    def get_item(self, key):
        res = self._data.get(key)
        if res is None or (time.time() - res[0]) > self._cache_lifetime:
            return None
        else:
            return res[1] 

    def cache_it(self, key, value):
        with self.lock:
            if len(self._heap) >= self._capacity:
                borning_time, old_key = heapq.heappop()
                self._data.pop(old_key)

            self._data[key] = (time.time(), value)
            heapq.heappush(self._heap, (time.time(), key))


class Locator(object):

    cache = Cache()

    def __init__(self, cache_lifetime=10):
        self.cache.set_cache_lifetime(cache_lifetime)

    def resolve(self, name, endpoint, port):
        res = self.cache.get_item((name, endpoint, port))
        if res is not None:
            return res
        else:
            res = self._get_api(name, endpoint, port)
            self.cache.cache_it((name, endpoint, port), res)
            return res

    def _get_api(self, name, endpoint, port):
        try:
            locator_pipe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            locator_pipe.settimeout(4.0)
            locator_pipe.connect((endpoint, port))
            locator_pipe.send(msgpack.packb([0, 1, [name]]))
            #locator_pipe.send(Message(0, 1, [name]).pack())
            u = msgpack.Unpacker()
            msg = None
            while msg is None:
                response = locator_pipe.recv(80960)
                u.feed(response)
                msg = Message.initialize(u.next())
        except Exception as err:
            raise LocatorResolveError(name, endpoint, port, str(err))
        finally:
            locator_pipe.close()
        if msg.id == message.RPC_CHUNK:
            return msgpack.unpackb(msg.data)
        if msg.id == message.RPC_ERROR:
            raise Exception(msg.message)