#
#    Copyright (c) 2012+ Anton Tyurin <noxiouz@yandex.ru>
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

import datetime
import logging

from tornado.gen import Return
from tornado.ioloop import IOLoop
from tornado.iostream import StreamClosedError
from tornado.queues import Queue


from .trace import pack_trace
from .util import msgpack_packb
from ..common import CocaineErrno
from ..decorators import coroutine
from ..exceptions import ChokeEvent
from ..exceptions import CocaineError
from ..exceptions import InvalidMessageType
from ..exceptions import ServiceError

log = logging.getLogger("cocaine.channel")


class EmptyResponse(CocaineError):
    pass


class ProtocolError(CocaineError):
    __slots__ = ("category", "code", "reason")

    def __init__(self, code, reason=""):
        super(ProtocolError, self).__init__()
        self.category, self.code = code
        self.reason = reason


def streaming_protocol(name, payload):
    if name == "write":  # pragma: no cover
        return payload[0] if len(payload) == 1 else payload
    elif name == "error":
        return ProtocolError(*payload)
    elif name == "close":
        return EmptyResponse()


def primitive_protocol(name, payload):
    if name == "value":
        return payload[0] if len(payload) == 1 else payload
    elif name == "error":
        return ProtocolError(*payload)


def null_protocol(name, payload):
    return (name, payload)


def detect_protocol_type(rx_tree):
    for name, _ in rx_tree.values():
        if name == 'value':
            return primitive_protocol
        elif name == 'write':
            return streaming_protocol
    return null_protocol


class PrettyPrintable(object):
    def __repr__(self):
        return "<%s at %s %s>" % (
            type(self).__name__, hex(id(self)), self._format())

    def __str__(self):
        return "<%s %s>" % (type(self).__name__, self._format())

    def _format(self):
        raise NotImplementedError


class Rx(PrettyPrintable):
    def __init__(self, rx_tree, io_loop=None, servicename=None):
        # If it's not the main thread
        # and a current IOloop doesn't exist here,
        # IOLoop.instance becomes self._io_loop
        self._io_loop = io_loop or IOLoop.current()
        self._queue = Queue()
        self._done = False
        self.servicename = servicename
        self.rx_tree = rx_tree
        self.default_protocol = detect_protocol_type(rx_tree)

    @coroutine
    def get(self, timeout=0, protocol=None):
        if self._done and self._queue.empty():
            raise ChokeEvent()

        # to pull variuos service errors
        if timeout <= 0 or timeout is None:
            item = yield self._queue.get()
        else:
            deadline = datetime.timedelta(seconds=timeout)
            item = yield self._queue.get(deadline)

        if isinstance(item, Exception):
            raise item

        if protocol is None:
            protocol = self.default_protocol

        name, payload = item
        res = protocol(name, payload)
        if isinstance(res, ProtocolError):
            raise ServiceError(self.servicename, res.reason,
                               res.code, res.category)
        else:
            raise Return(res)

    def done(self):
        self._done = True

    def push(self, msg_type, payload):
        dispatch = self.rx_tree.get(msg_type)
        log.debug("dispatch %s %.300s", dispatch, payload)
        if dispatch is None:
            raise InvalidMessageType(self.servicename, CocaineErrno.INVALIDMESSAGETYPE,
                                     "unexpected message type %s" % msg_type)
        name, rx = dispatch
        log.debug("name `%s` rx `%s`", name, rx)
        self._queue.put_nowait((name, payload))
        if rx == {}:  # the last transition
            self.done()
        elif rx is not None:  # not a recursive transition
            self.rx_tree = rx

    def error(self, err):
        self._queue.put_nowait(err)

    def closed(self):
        return self._done

    def _format(self):
        return "name: %s, queue: %s, done: %s" % (
            self.servicename, self._queue, self._done)


class Tx(PrettyPrintable):
    def __init__(self, tx_tree, pipe, session_id):
        self.tx_tree = tx_tree
        self.session_id = session_id
        self.pipe = pipe
        self._done = False

    @coroutine
    def _invoke(self, method_name, *args, **kwargs):
        trace = kwargs.get("trace")
        if self._done:
            raise ChokeEvent()

        if self.pipe is None:
            raise StreamClosedError()

        log.debug("_invoke has been called %.300s %.300s", str(args), str(kwargs))
        for method_id, (method, tx_tree) in self.tx_tree.items():  # py3 has no iteritems
            if method == method_name:
                log.debug("method `%s` has been found in API map", method_name)
                if trace is None:
                    self.pipe.write(msgpack_packb([self.session_id, method_id, args]))
                else:
                    self.pipe.write(msgpack_packb([self.session_id, method_id, args, pack_trace(trace)]))
                if tx_tree == {}:  # last transition
                    self.done()
                elif tx_tree is not None:  # not a recursive transition
                    self.tx_tree = tx_tree
                raise Return(None)
        raise AttributeError(method_name)

    def __getattr__(self, name):
        def on_getattr(*args, **kwargs):
            return self._invoke(name, *args, **kwargs)
        return on_getattr

    def done(self):
        self._done = True

    def _format(self):
        return "session_id: %d, pipe: %s, done: %s" % (
            self.session_id, self.pipe, self._done)


class Channel(PrettyPrintable):
    def __init__(self, rx, tx):
        self.rx = rx
        self.tx = tx

    def _format(self):
        return "tx: %s, rx: %s" % (self.tx, self.rx)
