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

import traceback

from decorators import default
from cocaine.exceptions import *
from cocaine.logger import Logger

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
        self.worker = worker
        self.session = session

    def write(self, chunk):
        if self._m_state is not None:
            self.worker.send_chunk(self.session, chunk)
            return
        assert (self._m_state is not None)
        traceback.print_stack()

    def close(self):
        if self._m_state is not None:
            self.worker.send_choke(self.session)
            self._m_state = None
            return
        assert (self._m_state is None)
        traceback.print_stack()

    @property
    def closed(self):
        return self._m_state is None

class Request(object):

    def __init__(self):
        self._logger = Logger()
        self.cache = list()
        self._clbk = None   # Callback - on chunk
        self._errbk = None  # Errorback - translate error to handler
        self._errmsg = None # Store message
        self._state = 1     # Status of stream (close/open)

    def push(self, chunk):
        if self._clbk is None:
            # If there is no attachment object, put chunk in the cache
            self._logger.debug("Cache chunk")
            self.cache.append(chunk)
        else:
            # Copy callback to temp, clear current callback and perform temp
            # Do it so because self._clbk may change, while perfoming callback function.
            # Avoid double chunk sending to the task
            self._logger.debug("Send chunk to application")
            temp = self._clbk
            self._clbk = None
            temp(chunk)

    def error(self, errormsg):
        self._errmsg = errormsg

    def close(self):
        self._logger.debug("Close request")
        self._state = None
        if len(self.cache) == 0 and self._clbk is not None:
            self._logger.warn("Chunks are over, but the application requests them")
            if self._errbk is not None:
                self._logger.error("Throw error")
                self._errbk(RequestError("No chunks are available"))
            else:
                self._logger.error("No errorback. Can't throw error")


    def read(self):
        def wrapper(clbk, errorback=None):
            self._read(clbk, errorback)
        return wrapper

    def _read(self, callback, errorback):
        if len(self.cache) > 0:
            callback(self.cache.pop(0))
        elif self._errmsg is not None:
            errorback(self._errmsg) #traslate error into worker
        elif self._state is not None:
            self._clbk = callback
            self._errbk = errorback
        else:
            #Stream closed by choke
            #Raise exception here because no chunks from cocaine-runtime are availaible
            self._logger.warn("Chunks are over, but the application requests them")
            errorback(RequestError("No chunks are available"))
