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

import msgpack

from cocaine.exceptions import RequestError
from cocaine.decorators import default
from cocaine.logging.log import core_log
from cocaine.futures import Deferred
from cocaine.futures import chain


class Sandbox(object):

    def __init__(self):
        self._events = dict()
        self._logger = core_log

    def invoke(self, event_name, request, stream):
        """ Connect worker and decorator """
        event_closure = self._events.get(event_name, None)
        if event_closure is not None:
            event_handler = event_closure()
            event_handler.invoke(request, stream)
        else:
            self._logger.warn("there is no handler for event %s" % event_name)
            # todo: define magic constants
            stream.error(-100, "there is no handler for event %s" % event_name)

    def on(self, event_name, event_handler):
        try:
            # Try to construct handler.
            closure = event_handler()
        except Exception:
            # If this callable object is not our wrapper - may raise Exception
            closure = default(event_handler)()
            if hasattr(closure, "_wrapped"):
                event_handler = default(event_handler)
        else:
            if not hasattr(closure, "_wrapped"):
                event_handler = default(event_handler)
        self._events[event_name] = event_handler


class Stream(object):

    def __init__(self, session, worker, event_name=""):
        self._m_state = 1
        self.worker = worker
        self.session = session
        self.event = event_name

    def write(self, chunk):
        chunk = msgpack.packb(chunk)
        if self._m_state is not None:
            self.worker.send_chunk(self.session, chunk)
            return
        traceback.print_stack()

    def close(self):
        if self._m_state is not None:
            self.worker.send_choke(self.session)
            self._m_state = None
            return
        traceback.print_stack()

    def error(self, code, message):
        if self._m_state is not None:
            self.worker.send_error(self.session, code, message)
            self.close()

    @property
    def closed(self):
        return self._m_state is None


class Request(Deferred):

    def __init__(self):
        self._logger = core_log
        self.cache = list()
        self._clbk = None   # Callback - on chunk
        self._errbk = None  # Errorback - translate error to handler
        self._errmsg = None  # Store message
        self._state = 1      # Status of stream (close/open)

    def push(self, chunk):
        if self._clbk is None:
            # If there is no attachment object, put chunk in the cache
            self._logger.debug("Cache chunk")
            self.cache.append(chunk)
        else:
            # Copy callback to temp, clear current callback and perform temp
            # Do it so because self._clbk may change,
            # while performing callback function.
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
            self._logger.warn("Chunks are over,\
                                but the application requests them")
            if self._errbk is not None:
                self._logger.error("Throw error")
                self._errbk(RequestError("No chunks are available"))
            else:
                self._logger.error("No errorback. Can't throw error")

    def read(self):
        return chain.Chain([lambda: self])

    def default_errorback(self, err):
        self._logger.error("No errorback.\
                Can't throw error: %s" % str(self._errmsg))

    def bind(self, callback, errorback=None, on_done=None):
        # self._logger.debug("Bind request")
        if len(self.cache) > 0:
            callback(self.cache.pop(0))
        elif self._errmsg is not None:
            if errorback is not None:
                errorback(self._errmsg)  # translate error into worker
            else:
                self.default_errorback(self._errmsg)
        elif self._state is not None:
            self._clbk = callback
            self._errbk = errorback or self.default_errorback
        else:
            # Stream closed by choke
            # Raise exception here because no chunks
            # from cocaine-runtime are available
            self._logger.warn("Chunks are over,\
                                but the application requests them")
            if errorback:
                errorback(RequestError("No chunks are available"))
