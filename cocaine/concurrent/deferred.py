#
#    Copyright (c) 2013+ Evgeny Safronov <division494@gmail.com>
#    Copyright (c) 2011-2013 Other contributors as noted in the AUTHORS file.
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

import collections
import functools
import logging
import types

from . import Future

__author__ = 'Evgeny Safronov <division494@gmail.com>'


log = logging.getLogger(__name__)


class Deferred(object):
    def __init__(self):
        self._callbacks = []
        self._pending = []

    def add_callback(self, callback):
        assert callable(callback)
        while len(self._pending) > 0:
            callback(self._pending.pop(0))
        self._callbacks.append(callback)

    def trigger(self, value=None):
        self._trigger(Future.Value(value))

    def error(self, err):
        self._trigger(Future.Error(err))

    def _trigger(self, result):
        if len(self._callbacks) == 0:
            self._pending.append(result)
        else:
            for callback in self._callbacks:
                callback(result)

    def close(self):
        while len(self._pending) > 0:
            result = self._pending.pop(0)
            for callback in self._callbacks:
                callback(result)
        self._callbacks = []


def _engine_closure(final_deferred):
    current_deferred = [None]
    deferred_results = collections.defaultdict(collections.deque)

    def _engine(future, g, deferred, tracked_deferreds):
        try:
            log.debug('== income deferred: %s, current: %s', deferred, current_deferred[0])
            if deferred == current_deferred[0]:
                log.debug('[<-] %s', future)
                try:
                    result = future.get()
                except StopIteration:
                    raise
                except Exception as err:
                    d = g.throw(err)
                else:
                    d = g.send(result)
                log.debug('[->] %s', d)
                current_deferred[0] = d

                while len(deferred_results[d]) > 0 and current_deferred[0] == d:
                    r = deferred_results[d].popleft()
                    log.debug('--- unwrap: %s from %s', r, d)
                    _engine(r, g, d, tracked_deferreds)

                if d not in tracked_deferreds:
                    log.debug('%s added in cache', d)
                    tracked_deferreds.add(d)
                    d.add_callback(functools.partial(_engine, g=g, deferred=d, tracked_deferreds=tracked_deferreds))
            else:
                log.debug('saving %s into %s list', future, deferred)
                deferred_results[deferred].append(future)
        except _ReturnEvent as event:
            log.debug(event)
            final_deferred.trigger(event.value)
        except StopIteration as err:
            log.debug('StopIteration - %r', err)
            final_deferred.trigger()
        except Exception as err:
            log.debug('error occurred - %s', err)
            final_deferred.error(err)
    return _engine


def engine(func):
    @functools.wraps(func)
    def unwind(*args, **kwargs):
        try:
            g = func(*args, **kwargs)
        except Exception as err:
            log.warn('failed to activate generator - %s', err)
            raise err
        else:
            assert isinstance(g, types.GeneratorType)
            d = Deferred()
            _engine_closure(d)(Future.Value(None), g, None, set())
            return d
    return unwind


class _ReturnEvent(StopIteration):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return '_ReturnEvent({0})'.format(self.value)


def return_(value):
    raise _ReturnEvent(value)