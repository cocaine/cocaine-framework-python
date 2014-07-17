#
#    Copyright (c) 2014+ Anton Tyurin <noxiouz@yandex.ru>
#    Copyright (c) 2014+ Evgeny Safronov <division494@gmail.com>
#    Copyright (c) 2011-2014 Other contributors as noted in the AUTHORS file.
#
#    This file is part of Cocaine.
#
#    Cocaine is free software; you can redistribute it and/or modify
#    it under the terms of the GNU Lesser General Public License as published
#    by the Free Software Foundation; either version 3 of the License, or
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

try:
    import asyncio
except ImportError:
    import trollius as asyncio


class Timer(object):
    def __init__(self, callback, period, loop=None):
        self.loop = loop or asyncio.get_event_loop()
        if period < 0:
            raise ValueError("Period must be a positive value")

        self.period = period
        self.callback = callback

        self._handler = None

    def start(self):
        if self._handler is None:
            self.schedule_next()
        else:
            raise Exception("Timer has already started")

    def stop(self):
        if self._handler is not None:
            self._handler.cancel()
            self._handler = None

    def schedule_next(self):
        self._handler = self.loop.call_later(self.period,
                                             self._run)

    def _run(self):
        try:
            self.callback()
        except Exception as err:
            context = {"message": str(err),
                       "exception": err,
                       "handle": self._handler}
            self.loop.call_exception_handler(context)
        self.schedule_next()
