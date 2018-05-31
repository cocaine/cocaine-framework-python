#
#    Copyright (c) 2012+ Anton Tyurin <noxiouz@yandex.ru>
#    Copyright (c) 2013+ Evgeny Safronov <division494@gmail.com>
#    Copyright (c) 2011-2014 Other contributors as noted in the AUTHORS file.
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
import logging
import socket
import warnings

import six

from tornado import gen
from tornado.ioloop import IOLoop
from tornado.iostream import IOStream

from .disowntimer import DisownTimer
from .message import Message
from .message import RPC
from .message import RPCv1
from .message import packv1
from .request import RequestStream
from .response import ResponseStream
from ..common import CocaineErrno
from ..decorators import coroutine
from ..detail.defaults import Defaults
from ..detail.headers import CocaineHeaders
from ..detail.iotimer import Timer
from ..detail.log import workerlog
from ..detail.util import msgpack_unpacker
from ..services import Service


DEFAULT_HEARTBEAT_TIMEOUT = 20
DEFAULT_DISOWN_TIMEOUT = 5


log = logging.getLogger('cocaine')


class TokenManager(object):
    """
    Represents authorization token manager interface which is responsible for fetching and
    updating auth tokens.

    Authorization systems are too different to create tiny abstraction to unite them. Some of them
    supports token refreshing, some does not. Instead of creating such abstraction layer we
    explicitly ask Cocaine Runtime which type of auth plugin is currently installed to select the
    proper way for token handling.
    """
    def token(self):
        raise NotImplementedError


class NullTokenManager(TokenManager):
    def token(self):
        return ''


class TicketVendingMachineTokenManager(TokenManager):
    def __init__(self, name, ticket, interval, loop=None):
        if loop:
            warnings.warn('loop argument is deprecated.', DeprecationWarning)
        loop = loop or IOLoop.current()
        self._name = name
        self._ticket = ticket
        self._service = Service('tvm')
        self._interval = interval

        loop.spawn_callback(self._refresh)

    def token(self):
        return self._ticket

    @coroutine
    def _refresh(self):
        while True:
            now = gen.sleep(self._interval)

            try:
                channel = yield self._service.refresh_ticket(
                    self._name,
                    self._ticket
                )
                self._ticket = yield channel.rx.get()
            except Exception as err:
                log.error('failed to refresh TVM ticket: %s', err)
            else:
                log.info('refreshed TVM ticket')
            yield now


def make_token_manager(name, token, loop=None):
    if loop:
        warnings.warn('io_loop argument is deprecated.', DeprecationWarning)
    loop = loop or IOLoop.current()
    if token.ty == 'TVM':
        return TicketVendingMachineTokenManager(name, token.body, 10.0, loop)
    else:
        return NullTokenManager()


class BasicWorker(object):
    def __init__(self, disown_timeout=DEFAULT_DISOWN_TIMEOUT,
                 heartbeat_timeout=DEFAULT_HEARTBEAT_TIMEOUT,
                 io_loop=None, app=None, uuid=None, endpoint=None):
        if heartbeat_timeout < disown_timeout:
            raise ValueError("heartbeat timeout must be greater than disown")

        self.appname = app or Defaults.app
        self.uuid = uuid or Defaults.uuid
        self.endpoint = endpoint or Defaults.endpoint

        if io_loop:
            warnings.warn('io_loop argument is deprecated.', DeprecationWarning)
        self.io_loop = io_loop or IOLoop.current()
        self._token_manager = make_token_manager(
            self.appname,
            Defaults.token(),
            self.io_loop
        )

        self.pipe = None
        self.buffer = msgpack_unpacker()

        self.disown_timer = Timer(self.on_disown, disown_timeout, self.io_loop)

        # it's a fallback mechanism to track
        # that we are disowned even when the main thread is blocked
        # 42 is the universal answer. It's the fallback mechanism
        self.threaded_disown_timer = DisownTimer(disown_timeout * 42)

        self.heartbeat_timer = Timer(self.on_heartbeat_timer,
                                     heartbeat_timeout, self.io_loop)

        # storehouse for sessions
        self.sessions = {}
        # handlers for events
        self._events = {}

        # avoid unnecessary dublicate packing of message
        self._heartbeat_msg = Message(RPC.HEARTBEAT, 1).pack()

        self._header_table = {
            'tx': CocaineHeaders(),
            'rx': CocaineHeaders(),
        }

    @coroutine
    def async_connect(self):
        sock = socket.socket(socket.AF_UNIX)
        workerlog.debug("connecting to %s", self.endpoint)
        try:
            io_stream = IOStream(sock, io_loop=self.io_loop)
            self.pipe = yield io_stream.connect(self.endpoint, callback=None)
            workerlog.debug("connected to %s %s", self.endpoint, self.pipe)
            self.pipe.read_until_close(callback=self.on_failure,
                                       streaming_callback=self.on_message)
        except Exception as err:
            workerlog.error("unable to connect to '%s' %s", self.endpoint, err)
            self.on_failure()
            return

        workerlog.debug("sending handshake")
        self.send_handshake()
        workerlog.debug("sending heartbeat")
        self.do_heartbeat()
        # start heartbeat timer
        self.heartbeat_timer.start()
        workerlog.debug("start threaded_disown_timer")
        self.threaded_disown_timer.start()

    @property
    def token(self):
        return self._token_manager.token()

    def run(self, binds=None):
        if binds is None:
            binds = {}
        # attach handlers
        for event, handler in six.iteritems(binds):
            self.on(event, handler)

        # schedule connection establishment
        self.async_connect()

        self.io_loop.start()

    def on(self, event_name, event_handler):
        event_name = six.b(event_name)
        workerlog.info("registering handler for event %s", event_name)
        self._events[event_name] = coroutine(event_handler)
        workerlog.info("handler for event %s has been attached", event_name)

    # Events
    # healthmonitoring events
    def on_heartbeat_timer(self):
        self.do_heartbeat()

    def on_disown(self):
        try:
            workerlog.error("disowned")
        finally:
            self._stop()

    # General dispatch method
    def on_message(self, data):
        workerlog.debug("on_message %.300s", data)
        self.buffer.feed(data)
        for i in self.buffer:
            workerlog.debug("unpacked %.300s", i)
            try:
                self.feed_message(i)
            except Exception as err:
                workerlog.warn("error %s occured while handling %.300s", err, i)

    def _dispatch_heartbeat(self, _):
        workerlog.debug("heartbeat has been received. Stop disown timer")
        self.threaded_disown_timer.notify()
        self.disown_timer.stop()

    def _dispatch_terminate(self, msg):
        workerlog.info("terminate has been received %s %s", msg.errno, msg.reason)
        self.terminate(msg.errno, msg.reason)

    def _dispatch_invoke(self, msg, headers):
        response = ResponseStream(msg.session, self, msg.event)
        try:
            workerlog.debug("invoke has been received %s", msg)
            request = RequestStream(headers, self._header_table['rx'])
            event_handler = self._events.get(msg.event)
            self.sessions[msg.session] = request

            @coroutine
            def start():
                if event_handler is not None:
                    future = event_handler(request, response)
                else:
                    future = self.fallback_handler(msg.event, request, response)

                try:
                    yield future
                    if not response.closed:
                        response.close()
                except Exception as err:
                    response.error(CocaineErrno.EUNCAUGHTEXCEPTION, str(err))

            start()
        except Exception as err:
            workerlog.exception("failed to invoke %s %s %s", msg.event, err, type(err))
            response.error(CocaineErrno.EINVFAILED, "failed to invoke %s" % err)

    def _dispatch_chunk(self, msg, headers):
        workerlog.debug("chunk has been received %d", msg.session)
        try:
            session = self.sessions[msg.session]
            session.push(msg.data, headers)
        except KeyError as err:
            workerlog.warning("no session %s", err)

    def _dispatch_choke(self, msg, headers):
        workerlog.debug("choke has been received %d", msg.session)
        session = self.sessions.pop(msg.session, None)
        if session is not None:
            session.close(headers)

    def _dispatch_error(self, msg, headers):
        workerlog.debug("dispatch error message %d: %d, %d, %s",
                        msg.session, msg.errno[0], msg.errno[1], msg.reason)
        session = self.sessions.pop(msg.session, None)
        if session is not None:
            session.error(msg.errno, msg.reason, headers)
            session.close(headers)

    def on_failure(self, *args):
        workerlog.error("connection has been lost")
        self.on_disown()

    def feed_message(self, message):
        raise NotImplementedError  # pragma: no cover

    def send_handshake(self):
        raise NotImplementedError  # pragma: no cover

    def send_heartbeat(self):
        raise NotImplementedError  # pragma: no cover

    def send_choke(self, session):
        raise NotImplementedError  # pragma: no cover

    def send_chunk(self, session, data):
        raise NotImplementedError  # pragma: no cover

    def send_error(self, session, category, code, msg):
        raise NotImplementedError  # pragma: no cover

    def send_terminate(self, code, reason):
        raise NotImplementedError  # pragma: no cover

    def terminate(self, code, reason):
        self.send_terminate(code, reason)
        self._stop()

    def do_heartbeat(self):
        self.disown_timer.start()
        workerlog.debug("heartbeat has been sent. Start disown timer")
        self.send_heartbeat()

    def _stop(self):
        self.threaded_disown_timer.stop()
        self.io_loop.stop()

    @coroutine
    def fallback_handler(self, event, _, response):
        response.error(CocaineErrno.ENOHANDLER, "there is no handler for event %s" % event)


class WorkerV1(BasicWorker):
    def __init__(self, *args, **kwargs):
        super(WorkerV1, self).__init__(*args, **kwargs)
        self.max_session = 0

    def send_handshake(self):
        self.pipe.write(packv1(1, RPCv1.HANDSHAKE, self.uuid))

    def send_heartbeat(self):
        self.pipe.write(packv1(1, RPCv1.HEARTBEAT))

    def send_choke(self, session):
        self.pipe.write(packv1(session, RPCv1.CLOSE))

    def send_chunk(self, session, data):
        self.pipe.write(packv1(session, RPCv1.WRITE, data))

    def send_error(self, session, category, code, msg):
        self.pipe.write(packv1(session, RPCv1.ERROR, (category, code), msg))

    def send_terminate(self, code, reason):
        self.pipe.write(packv1(1, RPCv1.TERMINATE, code, reason))

    def feed_message(self, msg):
        session, type_id, payload = msg[:3]
        if session == 1:
            if type_id == RPCv1.HEARTBEAT:
                self._dispatch_heartbeat(None)
            elif type_id == RPCv1.TERMINATE:
                self._dispatch_terminate(Message(RPC.TERMINATE, session, *payload))
            return

        headers = msg[3] if len(msg) > 3 else None
        if self.max_session < session:
            # it must be Invoke
            if type_id != RPCv1.INVOKE:
                workerlog.error("new session %d must start from invoke %d %s",
                                session, type_id, str(payload))
                return
            self.max_session = session
            self._dispatch_invoke(Message(RPC.INVOKE, session, *payload), headers)
            return

        if type_id == RPCv1.WRITE:
            self._dispatch_chunk(Message(RPC.CHUNK, session, *payload), headers)
        elif type_id == RPCv1.CLOSE:
            self._dispatch_choke(Message(RPC.CHOKE, session, *payload), headers)
        elif type_id == RPCv1.ERROR:
            self._dispatch_error(Message(RPC.ERROR, session, *payload), headers)
