import msgpack

from cocaine.asio import engine
from cocaine.tools import actions
from cocaine.tools.tags import GROUPS_TAGS

__author__ = 'EvgenySafronov <division494@gmail.com>'

GROUP_COLLECTION = 'groups'


class List(actions.List):
    def __init__(self, storage):
        super(List, self).__init__(GROUP_COLLECTION, GROUPS_TAGS, storage)


class View(actions.View):
    def __init__(self, storage, name):
        super(View, self).__init__(storage, GROUP_COLLECTION, name, 'groups')


class Create(actions.Specific):
    def __init__(self, storage, name):
        super(Create, self).__init__(storage, 'group', name)

    def execute(self):
        return self.storage.write(GROUP_COLLECTION, self.name, msgpack.dumps({}), GROUPS_TAGS)


class Remove(actions.Specific):
    def __init__(self, storage, name):
        super(Remove, self).__init__(storage, 'group', name)

    def execute(self):
        return self.storage.remove(GROUP_COLLECTION, self.name)


class Refresh(actions.Storage):
    def __init__(self, locator, storage, name):
        super(Refresh, self).__init__(storage)
        self.locator = locator
        self.name = name

    @engine.asynchronous
    def execute(self):
        names = yield List(self.storage).execute() if not self.name else [self.name]
        for name in names:
            yield self.locator.refresh(name)


class AddApplication(actions.Specific):
    def __init__(self, storage, name, app, weight):
        super(AddApplication, self).__init__(storage, 'group', name)
        self.app = app
        self.weight = int(weight)

    @engine.asynchronous
    def execute(self):
        group = yield self.storage.read(GROUP_COLLECTION, self.name)
        group = msgpack.loads(group)
        group[self.app] = self.weight
        yield self.storage.write(GROUP_COLLECTION, self.name, msgpack.dumps(group), GROUPS_TAGS)


class RemoveApplication(actions.Specific):
    def __init__(self, storage, name, app):
        super(RemoveApplication, self).__init__(storage, 'group', name)
        self.app = app

    @engine.asynchronous
    def execute(self):
        group = yield self.storage.read(GROUP_COLLECTION, self.name)
        group = msgpack.loads(group)
        if self.app in group:
            del group[self.app]
        yield self.storage.write(GROUP_COLLECTION, self.name, msgpack.dumps(group), GROUPS_TAGS)
