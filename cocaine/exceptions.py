#
#   Copyright (c) 2011-2013 Anton Tyurin <noxiouz@yandex.ru>
#   Copyright (c) 2011-2013 Evgeny Safronov <division494@gmail.com>
#   Copyright (c) 2011-2013 Other contributors as noted in the AUTHORS file.
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

__all__ = ["ServiceError", "RequestError", "LocatorResolveError"]


class CocaineError(Exception):
    """ Base exception """
    pass


class TimeoutError(CocaineError):
    pass


class RequestError(CocaineError):
    """Exception raised when u try to request chunks from closed request """

    def __init__(self, msg):
        self.msg = msg

    def __repr__(self):
        return "RequestError: %s" % self.msg

    def __str__(self):
        return "RequestError: %s" % self.msg


class ServiceError(CocaineError):
    """Exception raised when error message is received from service"""

    def __init__(self, servicename, msg, code):
        self.servicename = servicename
        self.msg = msg
        self.code = code

    def __repr__(self):
        return "ServiceException [%d] %s: %s" % (self.code, self.servicename, self.msg)

    def __str__(self):
        return "ServiceException [%d] %s: %s" % (self.code, self.servicename, self.msg)


class LocatorResolveError(CocaineError):
    """Raises when locator can not resolve service API"""

    def __init__(self, name, host, port, reason):
        message = 'unable to resolve API for service "%s" at %s:%d - %s' % (name, host, port, reason)
        super(LocatorResolveError, self).__init__(message)

    def __str__(self):
        return "LocatorResolveError: %s" % self.message

    def __repr__(self):
        return self.__str__()


class ConnectionError(Exception):
    pass


class AsyncConnectionTimeoutError(ConnectionError):

    def __init__(self, path):
        message = 'TimeOutError: {endpoint}'.format(endpoint=path)
        super(AsyncConnectionTimeoutError, self).__init__(message)


class AsyncConnectionError(ConnectionError):

    def __init__(self, path, errcode):
        message = 'ConnectionError: {endpoint} {error}'.format(endpoint=path, error=errcode)
        super(AsyncConnectionError, self).__init__(message)


############ PROTOCOL ############
class ChokeEvent(Exception):
    pass


############ COCAINE TOOL ERRORS ############
class ToolsError(CocaineError):
    pass


class UploadError(ToolsError):
    pass


class ServiceCallError(ToolsError):
    def __init__(self, serviceName, reason):
        super(ServiceCallError, self).__init__('error in service "{0}" - {1}'.format(serviceName, reason))
