#
#    Copyright (c) 2013+ Evgeny Safronov <division494@gmail.com>
#    Copyright (c) 2011-2013 Other contributors as noted in the AUTHORS file.
#
#    This file is part of Cocaine.
#
#    Cocaine is free software; you can redistribute it and/or modify
#    it under the terms of the GNU Lesser General Public License as published
#    by the Free Software Foundation; either version 3 of the License, or
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

__author__ = 'Evgeny Safronov <division494@gmail.com>'


class Future(object):
    def __init__(self):
        self._result = None
        self._is_error = False

    def set_value(self, result):
        self._result = result
        self._is_error = False

    def set_error(self, error):
        self._result = error
        self._is_error = True

    def get(self):
        if self._is_error:
            raise self._result
        else:
            return self._result

    @staticmethod
    def Value(value):
        result = Future()
        result.set_value(value)
        return result

    @staticmethod
    def Error(err):
        result = Future()
        result.set_error(err)
        return result

    def __str__(self):
        return 'Future(result={0})'.format(self._result)