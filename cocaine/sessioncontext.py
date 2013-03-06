# encoding: utf-8
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


from decorators import default

class Sandbox(object):

    def __init__(self):
        self._events = dict()

    def invoke(self, event_name, stream):
        """ Connect worker and decorator """
        event_handler = self._events.get(event_name, None)
        if event_name is not None:
            return event_handler.invoke(stream)
        assert (event_handler is not None)

    def on(self, event_name, event_handler):
        if not hasattr(event_handler, "_wrapped"):
            #event_handler = ProxyCoroutine(event_handler)
            event_handler = default(event_handler)
        self._events[event_name] = event_handler

class Stream(object):

    def __init__(self, session, worker):
        self._m_state = 1
        self.m_worker = worker
        self.m_session = session

    def push(self, chunk):
        #print "PUSH ME", chunk
        if self._m_state is not None:
            self.m_worker.send_chunk(self.m_session, chunk)
            return
        assert (self._m_state is not None)

    def close(self):
        if self._m_state is not None:
            self.m_worker.send_choke(self.m_session)
            self._m_state = None
            return
        assert (self._m_state is None)

    @property
    def closed(self):
        return self._m_state is None
