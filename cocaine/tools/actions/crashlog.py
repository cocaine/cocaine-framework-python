import time
from cocaine.futures.chain import Chain
from cocaine.tools import actions

__author__ = 'Evgeny Safronov <division494@gmail.com>'


class List(actions.Storage):
    def __init__(self, storage, **config):
        super(List, self).__init__(storage, **config)
        self.name = config.get('name')
        if not self.name:
            raise ValueError('Please specify crashlog name')

    def execute(self):
        return self.storage.find('crashlogs', (self.name, ))


def parseCrashlogs(crashlogs, timestamp=None):
    flt = lambda x: (x == timestamp if timestamp else True)
    _list = (log.split(':', 1) for log in crashlogs)
    return [(ts, time.ctime(float(ts) / 1000000), name) for ts, name in _list if flt(ts)]


class _Specific(actions.Storage):
    def __init__(self, storage, **config):
        super(_Specific, self).__init__(storage, **config)
        self.name = config.get('name')
        self.timestamp = config.get('manifest')
        if not self.name:
            raise ValueError('Please specify name')


class View(_Specific):
    def __init__(self, storage, **config):
        super(View, self).__init__(storage, **config)

    def execute(self):
        return Chain([self.do])

    def do(self):
        crashlogs = yield self.storage.find('crashlogs', (self.name,))
        parsedCrashlogs = parseCrashlogs(crashlogs, timestamp=self.timestamp)
        contents = []
        for crashlog in parsedCrashlogs:
            key = '%s:%s' % (crashlog[0], crashlog[2])
            content = yield self.storage.read('crashlogs', key)
            contents.append(content)
        yield ''.join(contents)


class Remove(_Specific):
    def __init__(self, storage, **config):
        super(Remove, self).__init__(storage, **config)

    def execute(self):
        return Chain([self.do])

    def do(self):
        crashlogs = yield self.storage.find('crashlogs', (self.name,))
        parsedCrashlogs = parseCrashlogs(crashlogs, timestamp=self.timestamp)
        for crashlog in parsedCrashlogs:
            key = '%s:%s' % (crashlog[0], crashlog[2])
            yield self.storage.remove('crashlogs', key)
        yield 'Done'


class RemoveAll(Remove):
    def __init__(self, storage, **config):
        config['manifest'] = None
        super(RemoveAll, self).__init__(storage, **config)