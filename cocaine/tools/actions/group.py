import msgpack

from cocaine.asio import engine
from cocaine.tools import actions

__author__ = 'EvgenySafronov <division494@gmail.com>'


class List(actions.List):
    def __init__(self, storage):
        super(List, self).__init__('groups', ['group'], storage)


class View(actions.View):
    def __init__(self, storage, name):
        super(View, self).__init__(storage, 'groups', name, 'groups')


class Create(actions.Specific):
    def __init__(self, storage, name):
        super(Create, self).__init__(storage, 'group', name)

    def execute(self):
        return self.storage.write('groups', self.name, msgpack.dumps({}), ['group'])


class Remove(actions.Specific):
    def __init__(self, storage, name):
        super(Remove, self).__init__(storage, 'group', name)

    def execute(self):
        return self.storage.remove('groups', self.name)


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
        group = yield self.storage.read('groups', self.name)
        group = msgpack.loads(group)
        group[self.app] = self.weight
        yield self.storage.write('groups', self.name, msgpack.dumps(group), ['group'])


class RemoveApplication(actions.Specific):
    def __init__(self, storage, name, app):
        super(RemoveApplication, self).__init__(storage, 'group', name)
        self.app = app

    @engine.asynchronous
    def execute(self):
        group = yield self.storage.read('groups', self.name)
        group = msgpack.loads(group)
        if self.app in group:
            del group[self.app]
        yield self.storage.write('groups', self.name, msgpack.dumps(group), ['group'])
