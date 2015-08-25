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

from .baseservice import BaseService
from .baseservice import TraceAdapter
from .defaults import Defaults
from .locator import Locator
from .util import create_new_io_loop

from ..decorators import coroutine
# cocaine defined exceptions
from ..exceptions import InvalidApiVersion


LOCATOR_DEFAULT_ENDPOINT = Defaults.locators
SYNC_CONNECTION_TIMEOUT = 5


class Service(BaseService):
    def __init__(self, name, endpoints=LOCATOR_DEFAULT_ENDPOINT,
                 seed=None, version=0, locator=None, io_loop=None, timeout=0):
        super(Service, self).__init__(name=name, endpoints=LOCATOR_DEFAULT_ENDPOINT, io_loop=io_loop)
        self.locator_endpoints = endpoints
        self.locator = locator
        self.timeout = timeout  # time for the resolve operation
        # Dispatch tree
        self.api = {}
        # Service API version
        self.version = version
        self.seed = seed

    @coroutine
    def connect(self, traceid=None):
        log = TraceAdapter(self.log, {"traceid": traceid}) if traceid else self.log

        log.debug("checking if service connected")
        if self._connected:
            log.debug("already connected")
            return

        log.info("resolving ...")
        # create locator here if it was not passed to us
        locator = self.locator or Locator(endpoints=self.locator_endpoints, io_loop=self.io_loop)
        try:
            if self.seed is not None:
                channel = yield locator.resolve(self.name, self.seed)
            else:
                channel = yield locator.resolve(self.name)
            # Set up self.endpoints for BaseService class
            # It's used in super(Service).connect()
            self.endpoints, version, self.api = yield channel.rx.get(timeout=self.timeout)
        finally:
            if self.locator is None:
                # disconnect locator as we created it
                locator.disconnect()

        log.info("successfully resolved %s", self.endpoints)
        log.debug("api: %s", self.api)

        # Version compatibility should be checked here.
        if not (self.version == 0 or version == self.version):
            raise InvalidApiVersion(self.name, version, self.version)
        yield super(Service, self).connect(traceid)


class SyncService(object):
    def __init__(self, *args, **kwargs):
        self._io_loop = kwargs.get("io_loop") or create_new_io_loop()
        kwargs["io_loop"] = self._io_loop
        timeout = kwargs.pop("connection_timeout", SYNC_CONNECTION_TIMEOUT)
        self._service = Service(*args, **kwargs)

        # establish connection
        self._io_loop.run_sync(self._service.connect, timeout=timeout)

    def __getattr__(self, name):
        def on_getattr(*args, **kwargs):
            return self._io_loop.run_sync(lambda: self._service._invoke(name, *args, **kwargs))
        return on_getattr

    def run_sync(self, future, timeout=None):
        return self._io_loop.run_sync(lambda: future, timeout=timeout)
