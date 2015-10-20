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
    Locator = {0: ['resolve', {}, {0: ['value', {}], 1: ['error', {}]}],
               1: ['connect', {}, {0: ['write', None], 1: ['error', {}], 2: ['close', {}]}],
               2: ['refresh', {}, {0: ['value', {}], 1: ['error', {}]}],
               3: ['cluster', {}, {0: ['value', {}], 1: ['error', {}]}],
               4: ['publish', {0: ['discard', {}]}, {0: ['value', {}], 1: ['error', {}]}],
               5: ['routing', {0: ['discard', {}]}, {0: ['write', None], 1: ['error', {}], 2: ['close', {}]}]}

    Logger = {0: ['emit', {}, {}],
              1: ['verbosity', {}, {0: ['value', {}], 1: ['error', {}]}],
              2: ['set_verbosity', {}, {0: ['value', {}], 1: ['error', {}]}]}
