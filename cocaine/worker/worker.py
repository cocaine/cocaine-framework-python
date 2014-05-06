#
#    Copyright (c) 2014+ Anton Tyurin <noxiouz@yandex.ru>
#    Copyright (c) 2014+ Evgeny Safronov <division494@gmail.com>
#    Copyright (c) 2011-2014 Other contributors as noted in the AUTHORS file.
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

import logging
import sys
import traceback

import asyncio

from ..asio.message import RPC
from ..asio.message import Message
from ..asio.utils import Timer
from ..asio import CocaineProtocol
from ._wrappers import default
from .response import ResponseStream
from .request import RequestStream

DEFAULT_HEARTBEAT_TIMEOUT = 20
DEFAULT_DISOWN_TIMEOUT = 5

logging.basicConfig()
log = logging.getLogger("asyncio")
log.setLevel(logging.DEBUG)


class Worker(object):
    def __init__(self, disown_timeout=DEFAULT_DISOWN_TIMEOUT,
                 heartbeat_timeout=DEFAULT_HEARTBEAT_TIMEOUT,
                 loop=None, **kwargs):
        if heartbeat_timeout < disown_timeout:
            raise ValueError("heartbeat timeout must be greater then disown")
        self.loop = loop or asyncio.get_event_loop()

        self.disown_timer = Timer(self.on_disown,
                                  disown_timeout, self.loop)

        self.heartbeat_timer = Timer(self.on_heartbeat_timer,
                                     heartbeat_timeout, self.loop)

        self._dispatcher = {
            RPC.HEARTBEAT: self._dispatch_heartbeat,
            RPC.TERMINATE: self._dispatch_terminate,
            RPC.INVOKE: self._dispatch_invoke,
            RPC.CHUNK: self._dispatch_chunk,
            # RPC.ERROR: self._dispatch_error,
            RPC.CHOKE: self._dispatch_choke
        }

        #TBD move into opts
        try:
            self.appname = kwargs.get("app") or sys.argv[sys.argv.index("--app") + 1]
            self.uuid = kwargs.get("uuid") or sys.argv[sys.argv.index("--uuid") + 1]
            self.endpoint = kwargs.get("endpoint") or sys.argv[sys.argv.index("--endpoint") + 1]
        except (ValueError, IndexError) as err:
            raise Exception("wrong commandline args %s" % err)

        # storehouse for sessions
        self.sessions = {}
        # handlers for events
        self._events = {}
        # protocol
        self.pr = None

        # avoid unnecessary dublicate packing of message
        self._heartbeat_msg = Message(RPC.HEARTBEAT, 0).pack()

    def async_connect(self):
        proto_factory = CocaineProtocol.factory(self.on_message,
                                                self.on_failure)

        @asyncio.coroutine
        def on_connect():
            log.debug("connecting to %s", self.endpoint)
            try:
                _, self.pr = yield self.loop.create_unix_connection(proto_factory,
                                                                    self.endpoint)
                log.debug("connected to %s", self.endpoint)
            except asyncio.FileNotFoundError as err:
                log.error("unable to connect to UNIX socket '%s'. No such file.",
                          self.endpoint)
            except Exception as err:
                log.error("unable to connect to '%s' %s", self.endpoint, err)
            else:
                self._send_handshake()
                self._send_heartbeat()
                return
            self.on_failure()

        asyncio.async(on_connect(), self.loop)

    def run(self, binds=None):
        if binds is None:
            binds = {}
        # attach handlers
        for event, handler in binds.iteritems():
            self.on(event, handler)

        # schedule connection establishment
        self.async_connect()
        # start heartbeat timer
        self.heartbeat_timer.start()

        if not self.loop.is_running():
            self.loop.run_forever()

    def on(self, event_name, event_handler):
        log.error(event_name)
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
        log.debug("Attach handler for %s", event_name)
        self._events[event_name] = event_handler

    # Events
    # healthmonitoring events
    def on_heartbeat_timer(self):
        self._send_heartbeat()

    def on_disown(self):
        try:
            log.error("disowned")
        finally:
            self._stop()

    # General dispathc method
    def on_message(self, args):
        log.debug("on_message")
        message = Message.initialize(args)
        callback = self._dispatcher.get(message.id)
        if callback is None:
            raise Exception("unknown message type %s" % str(message))

        callback(message)

    def terminate(self, code, reason):
        self.pr.write(Message(RPC.TERMINATE, 0,
                              code, reason).pack())
        self._stop()

    def _dispatch_heartbeat(self, _):
        log.debug("heartbeat has been received. Stop disown timer")
        self.disown_timer.stop()

    def _dispatch_terminate(self, msg):
        log.debug("terminate has been received %s %s", msg.reason, msg.message)
        self.terminate(msg.reason, msg.message)

    def _dispatch_invoke(self, msg):
        log.debug("invoke has been received %s", msg)
        request = RequestStream()
        response = ResponseStream(msg.session, self, msg.event)
        try:
            event_closure = self._events.get(msg.event, None)
            if event_closure is not None:
                event_handler = event_closure()
                event_handler.invoke(request, response, self.loop)
            else:
                self._logger.warn("there is no handler for event %s", msg.event)
                response.error(-100, "there is no handler for event %s", msg.event)

            self.sessions[msg.session] = request
        except (ImportError, SyntaxError) as err:
            response.error(2, "unrecoverable error: %s " % str(err))
            self.terminate(1, "Bad source code")
        except Exception as err:
            log.error("On invoke error: %s", err)
            traceback.print_stack()
            response.error(1, "Invocation error: %s" % err)

    def _dispatch_chunk(self, msg):
        log.debug("Receive chunk: %d", msg.session)
        try:
            _session = self.sessions[msg.session]
            _session.push(msg.data)
        except Exception as err:
            log.error("On push error: %s", err)
            # self.terminate(1, "Push error: %s" % str(err))
            return

    def _dispatch_choke(self, msg):
        log.debug("Receive choke: %d", msg.session)
        _session = self.sessions.get(msg.session, None)
        if _session is not None:
            _session.done()
            self.sessions.pop(msg.session)

    # On disconnection callback
    def on_failure(self, *args):
        log.error("connection has been lost")
        self.on_disown()

    # Private:
    def _send_handshake(self):
        self.pr.write(Message(RPC.HANDSHAKE, 0, self.uuid).pack())

    def _send_heartbeat(self):
        self.disown_timer.start()
        log.debug("heartbeat has been sent. Start disown timer")
        self.pr.write(self._heartbeat_msg)

    def send_choke(self, session):
        self.pr.write(Message(RPC.CHOKE, session).pack())

    def send_chunk(self, session, data):
        self.pr.write(Message(RPC.CHUNK, session, data).pack())

    def send_error(self, session, code, msg):
        self.pr.write(Message(RPC.ERROR, session, code, msg).pack())

    def _stop(self):
        self.loop.stop()
