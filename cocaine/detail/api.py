#
#    Copyright (c) 2012+ Anton Tyurin <noxiouz@yandex.ru>
#    Copyright (c) 2013+ Evgeny Safronov <division494@gmail.com>
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


class API(object):
    Locator = {0: [b'resolve', {}, {0: [b'value', {}], 1: [b'error', {}]}],
               1: [b'connect', {}, {0: [b'write', None], 1: [b'error', {}], 2: [b'close', {}]}],
               2: [b'refresh', {}, {0: [b'value', {}], 1: [b'error', {}]}],
               3: [b'cluster', {}, {0: [b'value', {}], 1: [b'error', {}]}],
               4: [b'publish', {0: [b'discard', {}]}, {0: [b'value', {}], 1: [b'error', {}]}],
               5: [b'routing', {0: [b'discard', {}]}, {0: [b'write', None], 1: [b'error', {}], 2: [b'close', {}]}],
               6: [b'uuid',    {}, {0: [b'value', {}], 1: [b'error', {}]}]
               }

    Logger = {0: [b'emit', {}, {}],
              1: [b'verbosity', {}, {0: [b'value', {}], 1: [b'error', {}]}],
              2: [b'set_verbosity', {}, {0: [b'value', {}], 1: [b'error', {}]}]}
