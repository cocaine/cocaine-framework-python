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

import logging
import threading

# from cocaine.services import SyncService
from cocaine.detail.util import create_new_io_loop

log = logging.getLogger("cocaine")
log.setLevel(logging.DEBUG)


# def test_sync_service():
#     s = SyncService("node")
#     for _ in range(5):
#         log.info("NEXT")
#         ls = s.run_sync(s.list().rx.get(), timeout=1)
#     assert isinstance(ls, list), ls


def test_create_new_io_loop():
    t = threading.Thread(target=create_new_io_loop)
    t.start()
    t.join()
