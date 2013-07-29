import msgpack
from cocaine.futures import chain

from cocaine.tools.actions import CocaineConfigReader
from cocaine.tools.tags import RUNLISTS_TAGS
from cocaine.tools import actions, log

__author__ = 'Evgeny Safronov <division494@gmail.com>'


class List(actions.List):
    def __init__(self, storage, **config):
        super(List, self).__init__('runlists', RUNLISTS_TAGS, storage, **config)


class Specific(actions.Storage):
    def __init__(self, storage, **config):
        super(Specific, self).__init__(storage, **config)
        self.name = config.get('name')
        if not self.name:
            raise ValueError('Please specify runlist name')


class View(Specific):
    def execute(self):
        return self.storage.read('runlists', self.name)


class Upload(Specific):
    def __init__(self, storage, **config):
        super(Upload, self).__init__(storage, **config)
        self.runlist = config.get('runlist')
        if not self.runlist:
            raise ValueError('Please specify runlist file path')

    def execute(self):
        runlist = CocaineConfigReader.load(self.runlist)
        return self.storage.write('runlists', self.name, runlist, RUNLISTS_TAGS)


class Create(Specific):
    def execute(self):
        runlist = msgpack.dumps({})
        return self.storage.write('runlists', self.name, runlist, RUNLISTS_TAGS)


class Remove(Specific):
    def execute(self):
        return self.storage.remove('runlists', self.name)


class AddApplication(Specific):
    def __init__(self, storage, **config):
        super(AddApplication, self).__init__(storage, **config)
        self.app = config.get('app')
        self.profile = config.get('profile')
        if not self.app:
            raise ValueError('Please specify application name')
        if not self.profile:
            raise ValueError('Please specify profile')

    @chain.source
    def execute(self):
        runlistInfo = yield View(self.storage, **{'name': self.name}).execute()
        runlist = msgpack.loads(runlistInfo)
        log.debug('Found runlist: {0}'.format(runlist))
        runlist[self.app] = self.profile
        runlistUploadAction = Upload(self.storage, **{
            'name': self.name,
            'runlist': runlist
        })
        yield runlistUploadAction.execute()
        result = {
            'runlist': self.name,
            'status': 'Success',
            'added': {
                'app': self.app,
                'profile': self.profile,
            }
        }
        yield result