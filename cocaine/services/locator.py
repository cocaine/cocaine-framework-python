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

from .base import AbstractService
from .state import RootState

__author__ = 'Evgeny Safronov <division494@gmail.com>'


log = logging.getLogger(__name__)


class RPC:
    PROTOCOL_LIST = (
        RESOLVE,
        SYNC,
        REPORTS,
        REFRESH,
    ) = range(4)


class Locator(AbstractService):
    """Represents locator service.

    Locator is the special service which can resolve other services in the cloud by name.

    .. note:: Normally, you shouldn't use this class directly - it is using behind the scene for resolving other
              services endpoints.
    """
    ROOT_STATE = RootState()

    def __init__(self):
        super(Locator, self).__init__('locator')

    def connect(self, host, port, timeout):
        """Connects to the locator at specified host and port.

        The locator itself always runs on a well-known host and port.

        :param host: locator hostname.
        :param port: locator port.
        :param timeout: connection timeout.
        """
        return self._connect_to_endpoint(host, port, timeout)

    def resolve(self, name, timeout):
        """Resolve service by its `name`.

        Returned tuple is describing resolved service information - `(endpoint, version, api)`:
         * `endpoint` - a 2-tuple containing `(host, port)` information about service endpoint.
         * `version` - an integer number showing actual service version.
         * `api` - a dict of number -> string structure, describing service's api.

        :param name: service name.
        :param timeout: resolving timeout.
        """
        log.debug('resolving %s', name)
        return self._invoke(RPC.RESOLVE, self.ROOT_STATE, name)

    def refresh(self, name, timeout=None):
        return self._invoke(RPC.REFRESH, self.ROOT_STATE, name)
