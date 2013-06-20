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

__all__ = ["ServiceError", "RequestError", "LocatorResolveError", "ConnectionRefusedError"]


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
    """ get_api failed """

    def __init__(self, servicename, host, port, reason=""):
        self.message = "Unable to resolve API for service\
        %s at %s:%d, because %s" % (servicename, host, port, reason) 

    def __str__(self):
        return "LocatorResolveError: %s" % self.message

    def __repr__(self):
        return self.__str__()

class ConnectionError(CocaineError):
    pass


class ConnectionRefusedError(ConnectionError):
    def __init__(self, host, port):
        message = 'Invalid cocaine-runtime endpoint: {host}:{port}'.format(host=host, port=port)
        super(ConnectionRefusedError, self).__init__(message)
