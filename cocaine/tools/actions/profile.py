import msgpack
from cocaine.tools.encoders import JsonEncoder
from cocaine.tools.tags import PROFILES_TAGS
from cocaine.tools import actions

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
        self.profileRaw = config.get('profile-raw')
        self.jsonEncoder = JsonEncoder()
        if not any([self.profile, self.profileRaw]):
            raise ValueError('Please specify profile file path')

    def execute(self):
        if self.profile:
            profile = self.jsonEncoder.encode(self.profile)
        else:
            profile = msgpack.dumps(self.profileRaw)
        return self.storage.write('profiles', self.name, profile, PROFILES_TAGS)


class Remove(Specific):
    def execute(self):
        return self.storage.remove('profiles', self.name)