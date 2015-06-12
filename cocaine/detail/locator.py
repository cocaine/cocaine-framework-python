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

from .api import API
from .baseservice import BaseService
from .defaults import Defaults

LOCATOR_DEFAULT_ENDPOINT = Defaults.locators


class Locator(BaseService):
    def __init__(self, endpoints=LOCATOR_DEFAULT_ENDPOINT, io_loop=None):
        super(Locator, self).__init__(name="locator",
                                      endpoints=endpoints, io_loop=io_loop)
        self.api = API.Locator
