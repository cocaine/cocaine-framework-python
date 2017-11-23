#
#    Copyright (c) 2012+ Anton Tyurin <noxiouz@yandex.ru>
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
import os
import sys
from collections import namedtuple

# ToDo: should I resolve hostname?
LOCATOR_DEFAULT_HOST = "127.0.0.1"
LOCATOR_DEFAULT_PORT = 10053
DEFAULT_APPNAME = "app/standalone"

TOKEN_TYPE_KEY = 'COCAINE_APP_TOKEN_TYPE'
TOKEN_BODY_KEY = 'COCAINE_APP_TOKEN_BODY'


_Token = namedtuple('Token', ['ty', 'body'])


def parse_locators_v1(inp):
    return [(host.strip("[]"), int(port)) for host, _, port in (s.rpartition(":") for s in inp.split(","))]


def parse_locators_v0(inp):
    host, _, port = inp.rpartition(":")
    return [(host, int(port))]


class GetOptError(ValueError):
    pass


class MalformedArgs(IndexError):
    pass


class DefaultOptions(object):
    def __init__(self, argv=None):
        self.argv = argv or sys.argv
        self._protocol = None
        self._endpoint = None
        self._uuid = None
        self._locators = None
        self._appname = None
        self._token = None

    def get_opt(self, name):
        try:
            return self.argv[self.argv.index(name) + 1]
        except ValueError:
            # no such option
            raise GetOptError("no such argument %s" % name)
        except IndexError:
            raise MalformedArgs("argument %s must have a value" % name)

    @property
    def protocol(self):
        if not self._protocol:
            try:
                self._protocol = int(self.get_opt("--protocol"))
            except GetOptError:
                self._protocol = 0
        return self._protocol

    @property
    def uuid(self):
        if not self._uuid:
            self._uuid = self.get_opt("--uuid")
        return self._uuid

    @property
    def locators(self):
        if not self._locators:
            try:
                value = self.get_opt("--locator")
                if self.protocol == 0:
                    self._locators = parse_locators_v0(value)
                elif self.protocol == 1:
                    self._locators = parse_locators_v1(value)
            except GetOptError:
                # we are not under cocaine
                self._locators = ((LOCATOR_DEFAULT_HOST, LOCATOR_DEFAULT_PORT), )
        return self._locators

    @property
    def endpoint(self):
        if not self._endpoint:
            self._endpoint = self.get_opt("--endpoint")
        return self._endpoint

    @property
    def app(self):
        if not self._appname:
            try:
                self._appname = self.get_opt("--app")
            except GetOptError:
                self._appname = DEFAULT_APPNAME
        return self._appname

    def token(self):
        """
        Returns authorization token provided by Cocaine.

        The real meaning of the token is determined by its type. For example OAUTH2 token will
        have "bearer" type.

        :return: A tuple of token type and body.
        """
        if self._token is None:
            token_type = os.getenv(TOKEN_TYPE_KEY, '')
            token_body = os.getenv(TOKEN_BODY_KEY, '')
            self._token = _Token(token_type, token_body)
        return self._token


Defaults = DefaultOptions()
