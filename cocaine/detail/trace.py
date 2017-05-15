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

import logging
import struct
from collections import namedtuple

import six

Trace = namedtuple('Trace', ['traceid', 'spanid', 'parentid'])


class TraceAdapter(logging.LoggerAdapter):
    def process(self, msg, kwargs):
        kwargs.setdefault("extra", {}).update(self.extra)
        return msg, kwargs


def get_trace_adapter(logger, trace_id):
    if trace_id is None:
        return logger
    if not isinstance(trace_id, six.string_types):
        trace_id = '{:016x}'.format(trace_id)
    return TraceAdapter(logger, {'trace_id': trace_id})


def pack_trace(trace):
    traceid = struct.pack("@Q", trace.traceid)
    spanid = struct.pack("@Q", trace.spanid)
    parentid = struct.pack("@Q", trace.parentid)
    return (False, 80, traceid), (False, 81, spanid), (False, 82, parentid)


def update_dict_with_trace(dict_, trace):
    dict_['trace_id'] = trace.traceid
    dict_['span_id'] = trace.spanid
    dict_['parent_id'] = trace.parentid
