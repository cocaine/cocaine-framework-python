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

from cocaine.detail.logger import _Logger
from cocaine.detail.service import EmptyResponse


def test_logger():
    verbosity_level = 0
    l = _Logger()
    empty_resp = l.set_verbosity(verbosity_level).wait(1).rx.get().wait(1)
    assert isinstance(empty_resp, EmptyResponse)
    verbosity = l.verbosity().wait(1).rx.get().wait(1)
    assert verbosity[0] == verbosity_level, verbosity
    l.emit(verbosity_level, "nosetest", "test_message", {"attr1": 1, "attr2": 2})
    l.debug("DEBUG_MSG", {"A": 1, "B": 2})
    l.info("INFO_MSG", {"A": 1, "B": 2})
    l.warning("WARNING_MSG", {"A": 1, "B": 2})
    l.error("ERROR_MSG", {"A": 1, "B": 2})
