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

import logging

# to avoid recursion when CocaineHandler is used
# ToDo: Logger must not be based on Service code
# to support Zipkin
cocainelog = logging.getLogger("cocaine")
cocainelog.propagate = False
if hasattr(logging, "NullHandler"):
    cocainelog.addHandler(logging.NullHandler())

servicelog = logging.getLogger("cocaine.baseservice")
workerlog = logging.getLogger("cocaine.worker")
# to log error events from a worker to a crashlog
workerlog.addHandler(logging.StreamHandler())
