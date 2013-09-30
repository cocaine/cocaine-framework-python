import msgpack

from cocaine.futures import chain
from cocaine.tools import actions, log
from cocaine.tools.actions import CocaineConfigReader
from cocaine.tools.tags import RUNLISTS_TAGS

__author__ = 'Evgeny Safronov <division494@gmail.com>'


class Specific(actions.Specific):
    def __init__(self, storage, name):
        super(Specific, self).__init__(storage, 'runlist', name)


class List(actions.List):
    def __init__(self, storage):
        super(List, self).__init__('runlists', RUNLISTS_TAGS, storage)


class View(actions.View):
    def __init__(self, storage, name):
        super(View, self).__init__(storage, 'runlist', name, 'runlists')


class Upload(Specific):
    def __init__(self, storage, name, runlist):
        super(Upload, self).__init__(storage, name)
        self.runlist = runlist
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
    def __init__(self, storage, name, app, profile, force=False):
        super(AddApplication, self).__init__(storage, name)
        self.app = app
        self.profile = profile
        self.force = force
        if not self.app:
            raise ValueError('Please specify application name')
        if not self.profile:
            raise ValueError('Please specify profile')

    @chain.source
    def execute(self):
        result = {
            'runlist': self.name,
            'status': 'modified',
            'added': {
                'app': self.app,
                'profile': self.profile,
            }
        }

        runlists = yield List(self.storage).execute()
        if self.force and self.name not in runlists:
            log.debug('Runlist does not exist. Creating new one ...')
            yield Create(self.storage, self.name).execute()
            result['status'] = 'created'

        runlistInfo = yield View(self.storage, name=self.name).execute()
        runlist = msgpack.loads(runlistInfo)
        log.debug('Found runlist: {0}'.format(runlist))
        runlist[self.app] = self.profile
        runlistUploadAction = Upload(self.storage, name=self.name, runlist=runlist)
        yield runlistUploadAction.execute()
        yield result