from cocaine.futures import chain
from cocaine.tools import actions
from cocaine.tools.actions import CocaineConfigReader, log
from cocaine.tools.tags import PROFILES_TAGS

__author__ = 'Evgeny Safronov <division494@gmail.com>'


class Specific(actions.Specific):
    def __init__(self, storage, name):
        super(Specific, self).__init__(storage, 'profile', name)


class List(actions.List):
    def __init__(self, storage):
        super(List, self).__init__('profiles', PROFILES_TAGS, storage)


class View(actions.View):
    def __init__(self, storage, name):
        super(View, self).__init__(storage, 'profile', name, 'profiles')


class Upload(Specific):
    def __init__(self, storage, name, profile):
        super(Upload, self).__init__(storage, name)
        self.profile = profile
        if not self.profile:
            raise ValueError('Please specify profile file path')

    @chain.source
    def execute(self):
        log.info('Uploading "%s"... ', self.name)
        profile = CocaineConfigReader.load(self.profile)
        yield self.storage.write('profiles', self.name, profile, PROFILES_TAGS)
        log.info('OK')


class Remove(Specific):
    @chain.source
    def execute(self):
        log.info('Removing "%s"... ', self.name)
        yield self.storage.remove('profiles', self.name)
        log.info('OK')