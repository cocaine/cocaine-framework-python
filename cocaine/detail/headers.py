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

# flake8: noqa

import collections
import six
import struct

# It is almost a plain copy from:
# https://github.com/python-hyper/hpack/blob/master/hpack/table.py
# with Cocaine specific headers in the STATIC_TABLE


class InvalidTableIndex(Exception):
    pass


def table_entry_size(name, value):
    """
    Calculates the size of a single entry

    This size is mostly irrelevant to us and defined
    specifically to accommodate memory management for
    lower level implementations. The 32 extra bytes are
    considered the "maximum" overhead that would be
    required to represent each entry in the table.

    See RFC7541 Section 4.1
    """
    return 32 + len(name) + len(value)


class CocaineHeaders(object):
    DEFAULT_SIZE = 4096

    STATIC_TABLE = (
        (b':authority'                  , b''             ),  # noqa
        (b':method'                     , b'GET'          ),  # noqa
        (b':method'                     , b'POST'         ),  # noqa
        (b':path'                       , b'/'            ),  # noqa
        (b':path'                       , b'/index.html'  ),  # noqa
        (b':scheme'                     , b'http'         ),  # noqa
        (b':scheme'                     , b'https'        ),  # noqa
        (b':status'                     , b'200'          ),  # noqa
        (b':status'                     , b'204'          ),  # noqa
        (b':status'                     , b'206'          ),  # noqa
        (b':status'                     , b'304'          ),  # noqa
        (b':status'                     , b'400'          ),  # noqa
        (b':status'                     , b'404'          ),  # noqa
        (b':status'                     , b'500'          ),  # noqa
        (b'accept-charset'              , b''             ),  # noqa
        (b'accept-encoding'             , b'gzip, deflate'),  # noqa
        (b'accept-language'             , b''             ),  # noqa
        (b'accept-ranges'               , b''             ),  # noqa
        (b'accept'                      , b''             ),  # noqa
        (b'access-control-allow-origin' , b''             ),  # noqa
        (b'age'                         , b''             ),  # noqa
        (b'allow'                       , b''             ),  # noqa
        (b'authorization'               , b''             ),  # noqa
        (b'cache-control'               , b''             ),  # noqa
        (b'content-disposition'         , b''             ),  # noqa
        (b'content-encoding'            , b''             ),  # noqa
        (b'content-language'            , b''             ),  # noqa
        (b'content-length'              , b''             ),  # noqa
        (b'content-location'            , b''             ),  # noqa
        (b'content-range'               , b''             ),  # noqa
        (b'content-type'                , b''             ),  # noqa
        (b'cookie'                      , b''             ),  # noqa
        (b'date'                        , b''             ),  # noqa
        (b'etag'                        , b''             ),  # noqa
        (b'expect'                      , b''             ),  # noqa
        (b'expires'                     , b''             ),  # noqa
        (b'from'                        , b''             ),  # noqa
        (b'host'                        , b''             ),  # noqa
        (b'if-match'                    , b''             ),  # noqa
        (b'if-modified-since'           , b''             ),  # noqa
        (b'if-none-match'               , b''             ),  # noqa
        (b'if-range'                    , b''             ),  # noqa
        (b'if-unmodified-since'         , b''             ),  # noqa
        (b'last-modified'               , b''             ),  # noqa
        (b'link'                        , b''             ),  # noqa
        (b'location'                    , b''             ),  # noqa
        (b'max-forwards'                , b''             ),  # noqa
        (b'proxy-authenticate'          , b''             ),  # noqa
        (b'proxy-authorization'         , b''             ),  # noqa
        (b'range'                       , b''             ),  # noqa
        (b'referer'                     , b''             ),  # noqa
        (b'refresh'                     , b''             ),  # noqa
        (b'retry-after'                 , b''             ),  # noqa
        (b'server'                      , b''             ),  # noqa
        (b'set-cookie'                  , b''             ),  # noqa
        (b'strict-transport-security'   , b''             ),  # noqa
        (b'transfer-encoding'           , b''             ),  # noqa
        (b'user-agent'                  , b''             ),  # noqa
        (b'vary'                        , b''             ),  # noqa
        (b'via'                         , b''             ),  # noqa
        (b'www-authenticate'            , b''             ),  # noqa
        (b''                            , b''             ),  # noqa
        (b''                            , b''             ),  # noqa
        (b''                            , b''             ),  # noqa
        (b''                            , b''             ),  # noqa
        (b''                            , b''             ),  # noqa
        (b''                            , b''             ),  # noqa
        (b''                            , b''             ),  # noqa
        (b''                            , b''             ),  # noqa
        (b''                            , b''             ),  # noqa
        (b''                            , b''             ),  # noqa
        (b''                            , b''             ),  # noqa
        (b''                            , b''             ),  # noqa
        (b''                            , b''             ),  # noqa
        (b''                            , b''             ),  # noqa
        (b''                            , b''             ),  # noqa
        (b''                            , b''             ),  # noqa
        (b''                            , b''             ),  # noqa
        (b''                            , b''             ),  # noqa
        (b'trace_id',  b'\x00\x00\x00\x00\x00\x00\x00\x00'),  # noqa
        (b'span_id',   b'\x00\x00\x00\x00\x00\x00\x00\x00'),  # noqa
        (b'parent_id', b'\x00\x00\x00\x00\x00\x00\x00\x00'),  # noqa
    )

    def __init__(self):
        self._maxsize = CocaineHeaders.DEFAULT_SIZE
        self._current_size = 0
        self.resized = False
        self.dynamic_entries = collections.deque()

    def get_by_index(self, index):
        """
        Returns the entry specified by index

        Note that the table is 1-based ie an index of 0 is
        invalid.  This is due to the fact that a zero value
        index signals that a completely unindexed header
        follows.

        The entry will either be from the static table or
        the dynamic table depending on the value of index.
        """
        index -= 1
        if 0 <= index < len(CocaineHeaders.STATIC_TABLE):
            return CocaineHeaders.STATIC_TABLE[index]
        index -= len(CocaineHeaders.STATIC_TABLE)
        if 0 <= index < len(self.dynamic_entries):
            return self.dynamic_entries[index]
        raise InvalidTableIndex("Invalid table index %d" % index)

    def __repr__(self):
        return "CocaineHeaders(%d, %s, %r)" % (
            self._maxsize,
            self.resized,
            self.dynamic_entries
        )

    def add(self, name, value):
        """
        Adds a new entry to the table

        We reduce the table size if the entry will make the
        table size greater than maxsize.
        """
        # We just clear the table if the entry is too big
        size = table_entry_size(name, value)
        if size > self._maxsize:
            self.dynamic_entries.clear()
            self._current_size = 0

        # Add new entry if the table actually has a size
        elif self._maxsize > 0:
            self.dynamic_entries.appendleft((name, value))
            self._current_size += size
            self._shrink()

    def search(self, name, value):
        """
        Searches the table for the entry specified by name
        and value

        Returns one of the following:
            - ``None``, no match at all
            - ``(index, name, None)`` for partial matches on name only.
            - ``(index, name, value)`` for perfect matches.
        """
        partial = None

        header_name_search_result = CocaineHeaders.STATIC_TABLE_MAPPING.get(name)
        if header_name_search_result:
            index = header_name_search_result[1].get(value)
            if index is not None:
                return index, name, value
            partial = (header_name_search_result[0], name, None)

        offset = len(CocaineHeaders.STATIC_TABLE)
        for (i, (n, v)) in enumerate(self.dynamic_entries):
            if n == name:
                if v == value:
                    return i + offset + 1, n, v
                elif partial is None:
                    partial = (i + offset + 1, n, None)
        return partial

    @property
    def maxsize(self):
        return self._maxsize

    @maxsize.setter
    def maxsize(self, newmax):
        newmax = int(newmax)
        oldmax = self._maxsize
        self._maxsize = newmax
        self.resized = (newmax != oldmax)
        if newmax <= 0:
            self.dynamic_entries.clear()
            self._current_size = 0
        elif oldmax > newmax:
            self._shrink()

    def _shrink(self):
        """
        Shrinks the dynamic table to be at or below maxsize
        """
        cursize = self._current_size
        while cursize > self._maxsize:
            name, value = self.dynamic_entries.pop()
            cursize -= table_entry_size(name, value)
        self._current_size = cursize

    def merge(self, raw_headers):
        # TODO: PY3: the static table contains only byte strings.
        # Seems values must be converted to bytestrings too.
        if raw_headers is None or len(raw_headers) == 0:
            return Headers()

        headers = Headers()
        for rh in raw_headers:
            if isinstance(rh, six.integer_types):
                headers.add(*self.get_by_index(rh))
            elif isinstance(rh, (list, tuple)) and len(rh) == 3:
                store, header, value = rh
                if isinstance(header, six.integer_types):
                    header, _ = self.get_by_index(header)
                else:
                    header = header

                if store:
                    self.add(header, value)
                headers.add(header, value)
        return headers


def _build_static_table_mapping():
    """
    Build static table mapping from header name to tuple with next structure:
    (<minimal index of header>, <mapping from header value to it index>).

    static_table_mapping used for hash searching.
    """
    static_table_mapping = {}
    for index, (name, value) in enumerate(CocaineHeaders.STATIC_TABLE, 1):
        header_name_search_result = static_table_mapping.setdefault(name, (index, {}))
        header_name_search_result[1][value] = index
    return static_table_mapping


CocaineHeaders.STATIC_TABLE_MAPPING = _build_static_table_mapping()


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


class Headers(collections.MutableMapping):
    def __init__(self, *args, **kwargs):
        self._dict = {}  # type: typing.Dict[str, str]
        self._as_list = {}  # type: typing.Dict[str, typing.List[str]]
        self._last_key = None
        if (len(args) == 1 and len(kwargs) == 0 and
                isinstance(args[0], Headers)):
            # Copy constructor
            for k, v in args[0].get_all():
                self.add(k, v)
        else:
            # Dict-style initialization
            self.update(*args, **kwargs)

    def add(self, name, value):
        # type: (str, str) -> None
        """Adds a new value for the given key."""
        self._last_key = name
        if name in self:
            self._dict[name] = value
            self._as_list[name].append(value)
        else:
            self[name] = value

    def get_list(self, name):
        """Returns all values for the given header as a list."""
        return self._as_list.get(name, [])

    def get_all(self):
        # type: () -> typing.Iterable[typing.Tuple[str, str]]
        """Returns an iterable of all (name, value) pairs.

        If a header has multiple values, multiple pairs will be
        returned with the same name.
        """
        for name, values in six.iteritems(self._as_list):
            for value in values:
                yield (name, value)

    def __setitem__(self, name, value):
        self._dict[name] = value
        self._as_list[name] = [value]

    def __getitem__(self, name):
        # type: (str) -> str
        return self._dict[name]

    def __delitem__(self, name):
        del self._dict[name]
        del self._as_list[name]

    def __len__(self):
        return len(self._dict)

    def __iter__(self):
        return iter(self._dict)

    def copy(self):
        # defined in dict but not in MutableMapping.
        return Headers(self)

    # Use our overridden copy method for the copy.copy module.
    # This makes shallow copies one level deeper, but preserves
    # the appearance that HTTPHeaders is a single container.
    __copy__ = copy

    def __str__(self):
        lines = []
        for name, value in self.get_all():
            lines.append("%s: %s\n" % (name, value))
        return "".join(lines)

    __unicode__ = __str__

    __repr__ = __str__
