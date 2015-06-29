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


class CocaineErrno(object):
    # no handler for requested event
    ENOHANDLER = 200
    # syntax error or import error
    EBADSOURCE = 210
    # invocation failed
    EINVFAILED = 212
    # service is disconnected
    ESRVDISCON = 220
    # service api version is unexpected
    INVALIDAPIVERSION = 230
    # message type is out of protocol
    INVALIDMESSAGETYPE = 240
    # uncaught exception
    EUNCAUGHTEXCEPTION = 100


class ErrorCategory(object):
    CFRAMEWORKCATEGORY = 42
