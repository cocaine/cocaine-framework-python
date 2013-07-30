from cocaine.tools.actions import CocaineConfigReader
from cocaine.tools.tags import PROFILES_TAGS
from cocaine.tools import actions

__author__ = 'Evgeny Safronov <division494@gmail.com>'


class List(actions.List):
    def __init__(self, storage):
        super(List, self).__init__('profiles', PROFILES_TAGS, storage)


class Specific(actions.Storage):
    def __init__(self, storage, name):
        super(Specific, self).__init__(storage)
        self.name = name
        if not self.name:
            raise ValueError('Please specify profile name')


class View(Specific):
    def execute(self):
        return self.storage.read('profiles', self.name)


class Upload(Specific):
    def __init__(self, storage, name, profile):
        super(Upload, self).__init__(storage, name)
        self.profile = profile
        if not self.profile:
            raise ValueError('Please specify profile file path')

    def execute(self):
        profile = CocaineConfigReader.load(self.profile)
        return self.storage.write('profiles', self.name, profile, PROFILES_TAGS)


class Remove(Specific):
    def execute(self):
        return self.storage.remove('profiles', self.name)