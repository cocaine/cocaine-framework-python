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

__all__ = ["ServiceError", "RequestError"]


class CocaineError(Exception):
    """Base exception"""
    pass


class RequestError(CocaineError):
    """Exception raised when u try to request chunks from closed request """
    def __init__(self, reason):
        super(RequestError, self).__init__('request error - {0}'.format(reason))


class ServiceError(CocaineError):
    """Exception raised when error message is received from service"""
    def __init__(self, servicename, reason, code):
        self.servicename = servicename
        self.code = code
        self.msg = reason
        super(ServiceError, self).__init__('error in service "{0}" - {1} [{2}]'.format(servicename, reason, code))


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


class ChokeEvent(Exception):
    def __str__(self):
        return 'ChokeEvent'
