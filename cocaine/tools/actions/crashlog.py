import time
from cocaine.asio import engine

from cocaine.futures import chain
from cocaine.tools import actions
from cocaine.tools.actions import app

__author__ = 'Evgeny Safronov <division494@gmail.com>'


class List(actions.Storage):
    def __init__(self, storage, name):
        super(List, self).__init__(storage)
        self.name = name
        if not self.name:
            raise ValueError('Please specify crashlog name')

    def execute(self):
        return self.storage.find('crashlogs', [self.name])


def _parseCrashlogs(crashlogs, timestamp=None):
    isFilter = lambda x: (x == timestamp if timestamp else True)
    _list = (log.split(':', 1) for log in crashlogs)
    return [(ts, time.ctime(float(ts) / 1000000), name) for ts, name in _list if isFilter(ts)]


class Specific(actions.Storage):
    def __init__(self, storage, name, timestamp=None):
        super(Specific, self).__init__(storage)
        self.name = name
        self.timestamp = timestamp
        if not self.name:
            raise ValueError('Please specify application name')


class View(Specific):
    @chain.source
    def execute(self):
        crashlogs = yield self.storage.find('crashlogs', [self.name])
        parsedCrashlogs = _parseCrashlogs(crashlogs, timestamp=self.timestamp)
        contents = []
        for crashlog in parsedCrashlogs:
            key = '%s:%s' % (crashlog[0], crashlog[2])
            content = yield self.storage.read('crashlogs', key)
            contents.append(content)
        yield ''.join(contents)


class Remove(Specific):
    @chain.source
    def execute(self):
        crashlogs = yield self.storage.find('crashlogs', [self.name])
        parsedCrashlogs = _parseCrashlogs(crashlogs, timestamp=self.timestamp)
        for crashlog in parsedCrashlogs:
            key = '%s:%s' % (crashlog[0], crashlog[2])
            yield self.storage.remove('crashlogs', key)
        yield 'Done'


class RemoveAll(Remove):
    def __init__(self, storage, name):
        super(RemoveAll, self).__init__(storage, name, timestamp=None)


class Status(actions.Storage):
    @engine.asynchronous
    def execute(self):
        applications = yield app.List(self.storage).execute()
        crashed = []
        for application in applications:
            crashlogs = yield List(self.storage, application).execute()
            if crashlogs:
                last = max(_parseCrashlogs(crashlogs), key=lambda (timestamp, time, uuid): timestamp)
                crashed.append((application, last, len(crashlogs)))
        yield crashed

