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

    def invoke(self, event_name, request, stream):
        """ Connect worker and decorator """
        event_handler = self._events.get(event_name, None)
        if event_name is not None:
            event_handler.invoke(request, stream)
        assert (event_handler is not None)

    def on(self, event_name, event_handler):
        if not hasattr(event_handler, "_wrapped"):
            event_handler = default(event_handler)
        self._events[event_name] = event_handler

class Stream(object):

    def __init__(self, session, worker):
        self._m_state = 1
        self.m_worker = worker
        self.m_session = session

    def push(self, chunk):
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

class Request(object):

    def __init__(self):
        self.m_cache = list()
        self._clbk = None
        self._state = 1

    def push(self, chunk):
        if self._clbk is None:
            #print "Save chunk in cache"
            self.m_cache.append(chunk)
        else:
            #print "Push chunk to clbk directly"
            self._clbk(chunk)

    def read(self):
        return self

    def close(self):
        #print "close by choke"
        self._state = None

    def __call__(self, clbk):
        if len(self.m_cache) > 0:
            print "Push from cache:"
            clbk(self.m_cache.pop(0))
        elif self._state is not None:
            print "Bind callback"
            self._clbk = clbk
        #Raise exception here because no chunks from cocaine-runtime are availaible
        #raise
