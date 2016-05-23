#
#    Copyright (c) 2011-2012 Andrey Sibiryov <me@kobology.ru>
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

from ..common import CocaineErrno

__author__ = 'Evgeny Safronov <division494@gmail.com>'


DEFAULT_FRAMEWORK_CATEGORY = 999


class CocaineError(Exception):
    pass


class InvalidChunk(CocaineError):
    def __str__(self):
        return "chunk must be string or bytes"


class ServiceError(CocaineError):
    def __init__(self, servicename, reason, code, category=DEFAULT_FRAMEWORK_CATEGORY):
        self.servicename = servicename
        self.code = code
        self.reason = reason
        self.category = category
        super(ServiceError, self).__init__('error in service "{0}" - {1} [{2}]'.format(servicename, reason, code))


class InvalidApiVersion(ServiceError):
    def __init__(self, servicename, expected_version, got_version):
        message = "invalid API version: expected `%d`, got `%d`" % (expected_version, got_version)
        super(InvalidApiVersion, self).__init__(servicename, message, CocaineErrno.INVALIDAPIVERSION)


class InvalidMessageType(ServiceError):
    pass


class ChokeEvent(CocaineError):
    pass


class ServiceConnectionError(CocaineError):
    def __init__(self, message):
        super(ServiceConnectionError, self).__init__(message)


class DisconnectionError(ServiceConnectionError):
    def __init__(self, name):  # pragma: no cover
        super(DisconnectionError, self).__init__('Service {0} has been disconnected'.format(name))
