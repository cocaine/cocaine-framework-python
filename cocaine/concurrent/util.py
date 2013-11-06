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

import functools

from ..concurrent import Deferred

__author__ = 'Evgeny Safronov <division494@gmail.com>'


class AllError(Exception):
    def __init__(self, results):
        super(AllError, self).__init__()
        self.results = results


class All(Deferred):
    def __init__(self, deferreds):
        super(All, self).__init__()
        assert all(map(lambda df: isinstance(df, Deferred), deferreds)), 'all items must be `Deferred` or extend it'
        self.deferreds = deferreds
        self.results = [None] * len(deferreds)
        self.done = [False] * len(deferreds)
        for pos, df in enumerate(deferreds):
            df.add_callback(functools.partial(self._collect, pos))

    def _collect(self, pos, result):
        try:
            self.results[pos] = result.get()
        except Exception as err:
            self.results[pos] = err
        self.done[pos] = True

        if all(self.done):
            if any(map(lambda r: isinstance(r, Exception) and not isinstance(r, StopIteration), self.results)):
                self.error(AllError(self.results))
            self.trigger(self.results)