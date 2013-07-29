import json
import msgpack
from cocaine.tools.actions import isJsonValid
from cocaine.tools.tags import PROFILES_TAGS
from cocaine.tools import actions, log

__author__ = 'Evgeny Safronov <division494@gmail.com>'


class List(actions.List):
    def __init__(self, storage, **config):
        super(List, self).__init__('profiles', PROFILES_TAGS, storage, **config)


class Specific(actions.Storage):
    def __init__(self, storage, **config):
        super(Specific, self).__init__(storage, **config)
        self.name = config.get('name')
        if not self.name:
            raise ValueError('Please specify profile name')


class View(Specific):
    def execute(self):
        return self.storage.read('profiles', self.name)


class Upload(Specific):
    def __init__(self, storage, **config):
        super(Upload, self).__init__(storage, **config)
        self.profile = config.get('manifest')
        if not self.profile:
            raise ValueError('Please specify profile file path')

    def execute(self):
        if isJsonValid(self.profile):
            log.debug('Profile specified directly')
            profile = self.profile
        else:
            log.debug('Loading profile from file ...')
            with open(self.profile, 'rb') as fh:
                profile = fh.read()
        encodedProfile = msgpack.dumps(json.loads(profile))
        return self.storage.write('profiles', self.name, encodedProfile, PROFILES_TAGS)


class Remove(Specific):
    def execute(self):
        return self.storage.remove('profiles', self.name)