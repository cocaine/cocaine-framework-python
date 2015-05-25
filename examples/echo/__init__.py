#!/usr/bin/env python

#    Copyright (c) 2014 Anton Tyurin <noxiouz@yandex.ru>
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

from cocaine.logger import Logger
from cocaine.worker import Worker

log = Logger()

def echo(request, response):
    log.info("start the request")
    inc = yield request.read()
    log.info("write a chunk")
    response.write(str(inc))
    log.info("close the request")
    response.close()


def main():
    w = Worker()
    w.on("ping", echo)
    w.run()


if __name__ == '__main__':
    main()
