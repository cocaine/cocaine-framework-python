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
import warnings

import six

from tornado.gen import Return
from tornado.ioloop import IOLoop
from tornado.iostream import StreamClosedError
from tornado.queues import Queue

from .headers import CocaineHeaders, pack_value
from .trace import get_trace_adapter, update_dict_with_trace
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
    if name == b"write":  # pragma: no cover
        return payload[0] if len(payload) == 1 else payload
    elif name == b"error":
        return ProtocolError(*payload)
    elif name == b"close":
        return EmptyResponse()


def primitive_protocol(name, payload):
    if name == b"value":
        return payload[0] if len(payload) == 1 else payload
    elif name == b"error":
        return ProtocolError(*payload)


def null_protocol(name, payload):
    return (name, payload)


def detect_protocol_type(rx_tree):
    for name, _ in six.itervalues(rx_tree):
        if name == b"value":
            return primitive_protocol
        elif name == b"write":
            return streaming_protocol
    return null_protocol


def manage_headers(headers, table):
    result = []
    for k, v in six.iteritems(headers):
        match = table.search(k, v)
        if match is None:
            # No match at all, add header into the table
            v = pack_value(k, v)
            table.add(k, v)
            result.append((True, k, v))
        else:
            idx, _, value = match
            if value is None:
                # Partial match by name.
                v = pack_value(k, v)
                table.add(k, v)
                result.append((True, idx, v))
            else:
                # Full match.
                result.append(idx)
    return result


class PrettyPrintable(object):
    def __repr__(self):
        return "<%s at %s %s>" % (
            type(self).__name__, hex(id(self)), self._format())

    def __str__(self):
        return "<%s %s>" % (type(self).__name__, self._format())

    def _format(self):
        raise NotImplementedError


class Rx(PrettyPrintable):
    def __init__(self, rx_tree, session_id, header_table=None, io_loop=None, service_name=None,
                 raw_headers=None, trace_id=None):
        if header_table is None:
            header_table = CocaineHeaders()

        if io_loop:
            warnings.warn('io_loop argument is deprecated.', DeprecationWarning)
        # If it's not the main thread
        # and a current IOloop doesn't exist here,
        # IOLoop.instance becomes self._io_loop
        self._io_loop = io_loop or IOLoop.current()
        self._queue = Queue()
        self._done = False
        self.session_id = session_id
        self.service_name = service_name
        self.rx_tree = rx_tree
        self.default_protocol = detect_protocol_type(rx_tree)
        self._headers = header_table
        self._current_headers = self._headers.merge(raw_headers)
        self.log = get_trace_adapter(log, trace_id)

    @coroutine
    def get(self, timeout=0, protocol=None):
        if self._done and self._queue.empty():
            raise ChokeEvent()

        # to pull various service errors
        if timeout <= 0:
            item = yield self._queue.get()
        else:
            deadline = datetime.timedelta(seconds=timeout)
            item = yield self._queue.get(deadline)

        if isinstance(item, Exception):
            raise item

        if protocol is None:
            protocol = self.default_protocol

        name, payload, raw_headers = item
        self._current_headers = self._headers.merge(raw_headers)
        res = protocol(name, payload)
        if isinstance(res, ProtocolError):
            raise ServiceError(self.service_name, res.reason, res.code, res.category)
        else:
            raise Return(res)

    def done(self):
        self._done = True

    def push(self, msg_type, payload, raw_headers):
        dispatch = self.rx_tree.get(msg_type)
        self.log.debug("dispatch %s %.300s", dispatch, payload)
        if dispatch is None:
            raise InvalidMessageType(self.service_name, CocaineErrno.INVALIDMESSAGETYPE,
                                     "unexpected message type %s" % msg_type)
        name, rx = dispatch
        self.log.info(
            "got message from `%s`: channel id: %s, type: %s",
            self.service_name,
            self.session_id,
            name
        )
        self._queue.put_nowait((name, payload, raw_headers))
        if rx == {}:  # the last transition
            self.done()
        elif rx is not None:  # not a recursive transition
            self.rx_tree = rx

    def error(self, err):
        self._queue.put_nowait(err)

    def closed(self):
        return self._done

    def _format(self):
        return "name: %s, queue: %s, done: %s" % (self.service_name, self._queue, self._done)

    @property
    def headers(self):
        return self._current_headers


class Tx(PrettyPrintable):
    def __init__(self, tx_tree, pipe, session_id, header_table, service_name, trace_id=None):
        self.tx_tree = tx_tree
        self.session_id = session_id
        self.service_name = service_name
        self.pipe = pipe
        self._done = False
        self._header_table = header_table
        self.trace_id = trace_id
        self.log = get_trace_adapter(log, trace_id)

    @coroutine
    def _invoke(self, method_name, *args, **kwargs):
        trace = kwargs.pop("trace", None)
        if trace:
            update_dict_with_trace(kwargs, trace)
        new_trace_id = kwargs.get('trace_id', self.trace_id)
        if new_trace_id != self.trace_id:
            self.log = get_trace_adapter(log, new_trace_id)
            self.trace_id = new_trace_id

        self.log.debug(
            "`%s` Tx method `%s` call: %.300s %.300s",
            self.service_name,
            method_name,
            args,
            kwargs
        )

        if self._done:
            raise ChokeEvent()

        if self.pipe is None:
            raise StreamClosedError()

        for method_id, (method, tx_tree) in six.iteritems(self.tx_tree):
            if method == method_name:
                self.log.debug("method `%s` has been found in API map", method_name)
                headers = manage_headers(kwargs, self._header_table)

                packed_data = msgpack_packb([self.session_id, method_id, args, headers])
                self.log.info(
                    'send message to `%s`: channel id: %s, type: %s, length: %s bytes',
                    self.service_name,
                    self.session_id,
                    method_name,
                    len(packed_data)
                )
                self.pipe.write(packed_data)

                if tx_tree == {}:  # last transition
                    self.done()
                elif tx_tree is not None:  # not a recursive transition
                    self.tx_tree = tx_tree
                raise Return(None)
        raise AttributeError(method_name)

    def __getattr__(self, name):
        def on_getattr(*args, **kwargs):
            return self._invoke(six.b(name), *args, **kwargs)
        return on_getattr

    def done(self):
        self._done = True

    def _format(self):
        return "session_id: %d, pipe: %s, done: %s" % (self.session_id, self.pipe, self._done)


class Channel(PrettyPrintable):
    def __init__(self, rx, tx):
        self.rx = rx
        self.tx = tx

    def _format(self):
        return "tx: %s, rx: %s" % (self.tx, self.rx)
