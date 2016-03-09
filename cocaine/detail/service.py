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

from ..decorators import coroutine
# cocaine defined exceptions
from ..exceptions import InvalidApiVersion


LOCATOR_DEFAULT_ENDPOINT = Defaults.locators
SYNC_CONNECTION_TIMEOUT = 5


class Service(BaseService):
    r"""Helper to interact with any Cocaine service.

    Creating new object does NOT establish a network connection.
    Service reestablishes the connection if it is not connected to Cocaine
    when any of its methods is being calling.
    """
    def __init__(self, name, endpoints=LOCATOR_DEFAULT_ENDPOINT,
                 seed=None, version=0, locator=None, io_loop=None, timeout=0):
        r"""Prepares new Service object.

        .. note::

            It never establishes any network connection in this method.
            The service is not resolved here.

        :param name: the name of the service
        :type name: str

        :param endpoints: list of suggested locator endpoints ("host", port).
        :type endpoints: tuple or list

        :param seed: seed is used to pin up a service version in case of resolving via routing group
        :type seed: int

        :param locator: Locator can be passed for resolving. The locator suppresses `endpoints` options.
        """
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
        r"""Connect resolves a service if the service is not connected.

        This method is supposed to be called rarely by a user
        as the framework keeps a conenction state.
        But if you need to get rid of connection delay, this method could be called explicitly.

        :param traceid: this value wiil be attached to logs of a connection process.
        :type traceid: int
        """
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
