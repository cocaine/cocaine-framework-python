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


class API:
    Locator = {
        0: [
            'resolve',
            {},
            {
                0: ['write', None, {}],
                1: ['error', {}, {}],
                2: ['close', {}, {}]
            }
        ],
        1: [
            'synchronize',
            {},
            {
                0: ['write', None, {}],
                1: ['error', {}, {}],
                2: ['close', {}, {}]
            }
        ],
        2: [
            'refresh',
            {
                0: ['write', None, {}],
                1: ['error', {}, {}],
                2: ['close', {}, {}]
            }
        ]
    }
