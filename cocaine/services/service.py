#
#    Copyright (c) 2013+ Evgeny Safronov <division494@gmail.com>
#    Copyright (c) 2011-2013 Other contributors as noted in the AUTHORS file.
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

from ..asio.exceptions import *
from ..concurrent import return_

from .base import AbstractService, LOCATOR_DEFAULT_HOST, LOCATOR_DEFAULT_PORT
from .exceptions import ServiceError
from .internal import strategy
from .locator import Locator
from .state import StateBuilder


__author__ = 'Evgeny Safronov <division494@gmail.com>'


log = logging.getLogger(__name__)


class Service(AbstractService):
    """Represents cocaine services or applications and provides API to communicate with them.

    This is the main class you will use to manage cocaine services in python. Let's start with the simple example:

    >>> from cocaine.services import Service
    >>> node = Service('node')

    We just created `node` service object by passing its name to the `cocaine.services.Service` initialization method.
    If no errors occurred, you can use it right now.

    If the service is not available, you will see something like that:

    >>> from cocaine.services import Service
    >>> node = Service('WAT?')
    Traceback (most recent call last):
    ...
    cocaine.exceptions.ServiceError: error in service "locator" - the specified service is not available [1]

    Behind the scene it has synchronously connected to the locator, resolved service's API and connected to the
    service's endpoint obtained by resolving. This is the normal usage of services.

    If you don't want immediate blocking service initialization, you can set `blockingConnect` argument to `False`
    and then to connect manually:

    >>> from cocaine.services import Service
    >>> node = Service('node', blockingConnect=False)
    >>> node.connect()

    You can also specify locator's address by passing `host` and `port` parameters like this:

    >>> from cocaine.services import Service
    >>> node = Service('node', host='localhost', port=666)

    .. note:: If you refused service connection-at-initialization, you shouldn't pass locator endpoint information,
              because this is mutual exclusive information. Specify them later when `connect` while method invoking.

    .. note:: If you don't want to create connection to the locator each time you create service, you can use
              `connectThroughLocator` method, which is specially designed for that cases.

    .. note:: Actual service's API is building dynamically. Sorry, IDE users, there is no autocompletion :(

    :ivar name: service or application name.
    :ivar version: service or application version. Provided only after its resolving.
    :ivar api: service or application API. Provided only after its resolving.
    """
    _locator_cache = {}

    def __init__(self, name, blockingConnect=True, host=LOCATOR_DEFAULT_HOST, port=LOCATOR_DEFAULT_PORT):
        super(Service, self).__init__(name)

        if not blockingConnect and any([host != LOCATOR_DEFAULT_HOST, port != LOCATOR_DEFAULT_PORT]):
            raise ValueError('you should not specify locator address in __init__ while performing non-blocking connect')

        if blockingConnect:
            self.connect(host, port, blocking=True)

    @strategy.coroutine
    def connect(self, host=LOCATOR_DEFAULT_HOST, port=LOCATOR_DEFAULT_PORT, timeout=None, blocking=False):
        """Connect to the service through locator and initialize its API.

        Before service is connected to its endpoint there is no any API (cause it's provided by locator). Any usage of
        uninitialized service results in `IllegalStateError`.

        .. note:: Note, that locator connection is created (and destroyed) each time you invoke this method.
                  If you don't want to create connection to the locator each time you create service, you can use
                  `connectThroughLocator` method, which is specially designed for that cases.
        """
        if (host, port) not in self._locator_cache:
            locator = Locator()
            self._locator_cache[(host, port)] = locator
        else:
            locator = self._locator_cache[(host, port)]

        if not locator.connected():
            yield locator.connect(host, port, timeout, blocking=blocking)
        yield self.connectThroughLocator(locator, timeout, blocking=blocking)

    @strategy.coroutine
    def connectThroughLocator(self, locator, timeout=None, blocking=False):
        try:
            endpoint, self.version, api = yield locator.resolve(self.name, timeout, blocking=blocking)
        except ServiceError as err:
            raise LocatorResolveError(self.name, locator.address, err)

        self.states = StateBuilder.build(api).substates
        for state in self.states.values():
            self.api[state.name] = state.id
            invoke = self._make_invokable(state)
            # invoke = self._make_reconnectable(invoke, locator)
            setattr(self, state.name, invoke)

        yield self._connect_to_endpoint(*endpoint, timeout=timeout, blocking=blocking)

    def _make_reconnectable(self, func, locator):
        @strategy.coroutine
        def wrapper(*args, **kwargs):
            if not self.connected():
                yield self.connectThroughLocator(locator)

            try:
                d = yield func(*args, **kwargs)
            except KeyError as fd:
                log.warn('broken pipe detected, fd: %s', str(fd))
                log.info('reconnecting... ')
                yield self.disconnect()
                yield self.connectThroughLocator(locator)
                d = yield func(*args, **kwargs)
                log.info('service has been successfully reconnected')
            return_(d)

        return wrapper

    @strategy.coroutine
    def reconnect(self, timeout=None, blocking=False):
        if self.connecting():
            raise IllegalStateError('already connecting')
        self.disconnect()
        yield self.connect(timeout=timeout, blocking=blocking)

    def __getattr__(self, item):
        def caller(*args, **kwargs):
            return self.enqueue(item, *args, **kwargs)
        return caller

    def _make_invokable(self, state):
        def wrapper(*args, **kwargs):
            if not self.connected():
                raise IllegalStateError('service "%s" is not connected', self.name)
            return self._invoke(state.id, state, *args, **kwargs)
        return wrapper

    def _make_chunk(self, method_id, session):
        def wrapper(*args, **kwargs):
            if not self.connected():
                raise IllegalStateError('service "%s" is not connected', self.name)
            return self._chunk(method_id, session, *args, **kwargs)
        return wrapper