# Copyright (c) 2012 Tyurin Anton noxiouz@yandex.ru
#
# This file is part of cocaine-tornado-proxy.
#
# cocaine-tornado-proxy is free software; you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# cocaine-tornado-proxy is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#

import random
import logging
import time
import re
import httplib
from functools import partial
from collections import defaultdict

import msgpack
import tornado.httpserver
import tornado.options
from tornado import ioloop


from cocaine.services import Service
from cocaine.exceptions import ServiceError
from cocaine.exceptions import ChokeEvent
from cocaine.futures import chain


RECONNECT_START = "Start asynchronous reconnect %s"
RECONNECT_SUCCESS = "Reconnect %s %d to %s successfully."
RECONNECT_FAIL = "Unable to reconnect %s, because %s"
NEXT_REFRESH = "Next update %d after %d second"

MOVE_TO_INACTIVE = "Move to inactive queue %s %s from pool with active %d"


logger = logging.getLogger(__name__)
io_loop = ioloop.IOLoop.instance()

URL_REGEX = re.compile(r"/([^/]*)/([^/?]*)(.*)")

DEFAULT_SERVICE_CACHE_COUNT = 5
DEFAULT_REFRESH_PERIOD = 10
DEFAULT_TIMEOUT = 1

cache = defaultdict(list)  # active applications
dying = defaultdict(list)  # application, which are waiting for reconnection


class CocaineProxy(object):
    TEMPLATE = "%(VERSION)s %(CODE)d %(STATUS)s\r\n%(HEADERS)s\r\n%(BODY)s"

    def __init__(self, port=8080, cache=DEFAULT_SERVICE_CACHE_COUNT, **config):
        self.port = port
        self.serviceCacheCount = cache
        self.spoolSize = int(self.serviceCacheCount * 1.5)
        self.refreshPeriod = config.get("refresh_timeout") or DEFAULT_REFRESH_PERIOD
        self.timeouts = config.get("timeouts", {})

    def get_timeout(self, name):
        return self.timeouts.get(name, DEFAULT_TIMEOUT)

    def async_reconnect(self, app, name):
        def callback(res):
            try:
                res.get()
                logger.info(RECONNECT_SUCCESS, app.name, id(app), "{0}:{1}".format(*app.address))
            except Exception as err:
                logger.warning(RECONNECT_FAIL, name, err)
            finally:
                dying[name].remove(app)
                cache[name].append(app)
                next_refresh = (1 + random.random()) * self.refreshPeriod
                logger.info(NEXT_REFRESH, id(app), next_refresh)
                io_loop.add_timeout(time.time() + next_refresh, self.move_to_inactive(app, name))
        try:
            logger.info(RECONNECT_START, app.name)
            app.reconnect(timeout=1.0, blocking=False).then(callback)
        except Exception as err:
            logger.exception(RECONNECT_FAIL, name, err)
            dying[name].remove(app)

    def move_to_inactive(self, app, name):
        def wrapper():
            active_apps = len(cache[name])
            if active_apps < self.serviceCacheCount:
                io_loop.add_timeout(time.time() + self.get_timeout(name) + 1, self.move_to_inactive(app, name))
                return
            logger.info(MOVE_TO_INACTIVE, app.name, "{0}:{1}".format(*app.address), active_apps)
            # Move service to sandbox for waiting current sessions
            try:
                inx = cache[name].index(app)
                # To avoid gc collect
                dying[name].append(cache[name].pop(inx))
            except ValueError:
                logger.error("Broken cache")
                return

            io_loop.add_timeout(time.time() + self.get_timeout(name) + 1, partial(self.async_reconnect, app, name))
        return wrapper

    def get_service(self, name):
        if len(cache[name]) < self.spoolSize - len(dying[name]):
            try:
                created = []
                for _ in xrange(self.spoolSize - len(cache[name])):
                    app = Service(name)
                    created.append(app)
                    logger.info("Connect to app: %s endpoint %s ", app.name, "{0}:{1}".format(*app.address))

                cache[name].extend(created)
                for app in created:
                    timeout = (1 + random.random()) * self.refreshPeriod
                    io_loop.add_timeout(time.time() + timeout, self.move_to_inactive(app, name))
            except Exception as err:
                logger.error(str(err))
                return None

        chosen = random.choice(cache[name])
        if chosen.isConnected():
            try:
                fd = chosen._pipe.sock.fileno()
                chosen._ioLoop._fd_events[fd]
            except Exception as err:
                logger.exception("Wrong fd or missing poll event, so remove this service")
                cache[name].remove(chosen)
                return self.get_service(name)
            return chosen
        else:
            logger.warning("Service %s disconnected %s", chosen.name, chosen.address)
            try:
                chosen.reconnect(blocking=True)
                if chosen.isConnected():
                    try:
                        fd = chosen._pipe.sock.fileno()
                        chosen._ioLoop._fd_events[fd]
                    except Exception as err:
                        logger.exception("Wrong fd or missing poll event, so remove this service")
                        cache[name].remove(chosen)
                        return self.get_service(name)
                    logger.info("Service %s has reconnected successfully", chosen.name)
                    return chosen
                else:
                    return None
            except Exception as err:
                return None

    @chain.source
    def process(self, obj, service, event, data):
        message_parts = []
        try:
            chunk = yield service.enqueue(event, msgpack.packb(data))
            while True:
                body = yield
                message_parts.append(str(body))
        except ChokeEvent as err:
            message = ''.join(message_parts)
            headers_from_app = '\r\n'.join(': '.join(_) for _ in chunk[1])
            if headers_from_app:
                headers = headers_from_app + '\r\nContent-Length: %d\r\n' % len(message)
            else:
                headers = 'Content-Length: %d\r\n' % len(message)
            response_data = self.TEMPLATE % {
                "VERSION": obj.version,
                "CODE": chunk[0],
                "STATUS": httplib.responses[chunk[0]],
                "HEADERS": headers,
                "BODY": message}
        except ServiceError as err:
            logger.error(str(err))
            message = "Application error: %s" % str(err)
            response_data = self.TEMPLATE % {
                "VERSION": obj.version,
                "CODE": 502,
                "STATUS": httplib.responses[502],
                "HEADERS": 'Content-Length: %d\r\n' % len(message),
                "BODY": message}
        except Exception as err:
            logger.error(err)
            message = "Unknown error: %s" % str(err)
            response_data = self.TEMPLATE % {
                "VERSION": obj.version,
                "CODE": 502,
                "STATUS": httplib.responses[502],
                "HEADERS": 'Content-Length: %d\r\n' % len(message),
                "BODY": message}
        if obj._finish_time is None:
            obj.write(response_data)
            obj.finish()

    def pack_httprequest(self, request):
        headers = [(item.key, item.value) for item in request.cookies.itervalues()]
        headers.extend(request.headers.iteritems())
        d = request.method, request.uri, request.version, headers, request.body
        return d

    def generate_info(self):
        msg = "ACTIVE SERVICES\n"
        for k, v in cache.iteritems():
            msg += "%s\n%s\n\n" % (k.upper(), '\n'.join("%s %d %s %s %d %s" % (
                app.name,
                id(app),
                '{0}:{1}'.format(*app.address),
                app.isConnected(),
                app._pipe.fileno() if app._pipe else -1,
                str(app._ioLoop._fd_events)) for app in v))
        msg += "\nINACTIVE SERVICES\n"
        for k, v in dying.iteritems():
            msg += "%s\n%s\n\n" % (k.upper(), '\n'.join("%s %d %s %s" % (
                app.name,
                id(app), '{0}:{1}'.format(*app.address),
                app.isConnected()) for app in v))
        return msg

    def handle_request(self, request):
        match = URL_REGEX.match(request.uri)

        if match is None:
            if request.path == "/info":
                message = self.generate_info()
                request.write("%s 200 OK\r\nContent-Length: %d\r\n\r\n%s" % (
                    request.version, len(message), message))
                request.finish()
                return

            message = "Invalid url"
            request.write("%s 404 Not found\r\nContent-Length: %d\r\n\r\n%s" % (
                request.version, len(message), message))
            request.finish()
            return

        name, event, other = match.groups()
        if name == '' or event == '':
            message = "Invalid request"
            request.write("%s 404 Not found\r\nContent-Length: %d\r\n\r\n%s" % (
                request.version, len(message), message))
            request.finish()
            return

        # Drop from query appname and event's name
        if not other.startswith('/'):
            other = "/%s" % other
        request.uri = other
        request.path = other.partition("?")[0]

        s = self.get_service(name)
        if s is None:
            message = "Current application %s is unavailable" % name
            request.write("%s 502 Not found\r\nContent-Length: %d\r\n\r\n%s" % (
                request.version, len(message), message))
            request.finish()
            return

        data = self.pack_httprequest(request)
        self.process(request, s, event, data)

    def run(self):
        http_server = tornado.httpserver.HTTPServer(self.handle_request, no_keep_alive=False, xheaders=True)
        http_server.listen(self.port)
        tornado.ioloop.IOLoop.instance().start()