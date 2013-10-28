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


class StateBuilder(object):
    @classmethod
    def build(cls, api):
        root = RootState()
        cls._build(root, api)
        return root

    @classmethod
    def _build(cls, parent, api):
        if api is None:
            return
        for id_, (name, api) in api.items():
            state = State(id_, name, parent)
            cls._build(state, api)


class State(object):
    def __init__(self, id_, name, parent=None):
        self.id = id_
        self.name = name
        self.substates = {}
        if parent is not None:
            parent.substates[name] = self

    def __str__(self):
        return 'State(id={0}, name={1}, substates={2})'.format(self.id, self.name, self.substates)

    def __repr__(self):
        return '<{0}>'.format(str(self))

    def __eq__(self, other):
        if other is None:
            return False
        return all([self.id == other.id,
                    self.name == other.name,
                    self.substates == other.substates])


class RootState(State):
    def __init__(self):
        super(RootState, self).__init__(0, '/', None)
