
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

from cocaine.detail.headers import CocaineHeaders


def test_extra_static_values():
    h = CocaineHeaders()
    assert len(CocaineHeaders.STATIC_TABLE) == 82, len(CocaineHeaders.STATIC_TABLE)
    assert h.get_by_index(80) == (b'trace_id', b'\x00\x00\x00\x00\x00\x00\x00\x00'), h.get_by_index(80)
    assert h.get_by_index(81) == (b'span_id', b'\x00\x00\x00\x00\x00\x00\x00\x00')
    assert h.get_by_index(82) == (b'parent_id', b'\x00\x00\x00\x00\x00\x00\x00\x00')
