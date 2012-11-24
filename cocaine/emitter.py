# encoding: utf-8
#
#    Copyright (c) 2011-2012 Andrey Sibiryov <me@kobology.ru>
#    Copyright (c) 2011-2012 Other contributors as noted in the AUTHORS file.
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

from collections import defaultdict

class EventSource(object):
    def __init__(self):
        self.slots = defaultdict(lambda: [])

    def on(self, event, callback):
        if callback in self.slots[event]:
            raise RuntimeError("duplicate callback")

        self.slots[event].append(callback)

    def invoke(self, event, *args, **kwargs):
        for callback in self.slots[event]:
            callback(*args, **kwargs)

