#
#    Copyright (c) 2012+ Anton Tyurin <noxiouz@yandex.ru>
#    Copyright (c) 2011-2016 Other contributors as noted in the AUTHORS file.
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

import struct

import six
from hpack.table import HeaderTable

_PACK_TRAITS = {
    'trace_id': 'Q',
    'span_id': 'Q',
    'parent_id': 'Q',
}


def pack_value(name, value):
    fmt = _PACK_TRAITS.get(name)
    if fmt is None:
        return value
    else:
        return struct.pack(fmt, value)


def synchronize_with_table(table, raw_headers):
    # TODO: PY3: the static table contains only byte strings.
    # Seems values must be converted to bytestrings too.
    if raw_headers is None or len(raw_headers) == 0:
        return HeaderTable()

    headers = HeaderTable()
    for rh in raw_headers:
        if isinstance(rh, six.integer_types):
            headers.add(*table.get_by_index(rh))
        elif isinstance(rh, (list, tuple)) and len(rh) == 3:
            store, header, value = rh
            if isinstance(header, six.integer_types):
                header, _ = table.get_by_index(header)
            else:
                header = six.b(header)

            if store:
                table.add(header, value)
            headers.add(header, value)
    return headers
