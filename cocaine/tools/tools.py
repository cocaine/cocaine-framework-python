import collections
import json
import socket
import errno
import sys
import tarfile
from time import ctime, time
from warnings import warn
from cocaine.futures import chain
from cocaine.futures.chain import ChainFactory

from cocaine.services import Service
import msgpack
from tornado.ioloop import IOLoop

from cocaine.exceptions import ConnectionRefusedError, ConnectionError
from cocaine.exceptions import CocaineError


APPS_TAGS = ("app",)
RUNLISTS_TAGS = ("runlist",)
PROFILES_TAGS = ("profile",)


class COLORED:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'

    def disable(self):
        self.HEADER = ''
        self.OKBLUE = ''
        self.OKGREEN = ''
        self.WARNING = ''
        self.FAIL = ''
        self.ENDC = ''
coloredOutput = COLORED()


def printError(message):
    sys.stderr.write('{s}{message}{e}\n'.format(s=coloredOutput.FAIL, message=message, e=coloredOutput.ENDC))


class StorageAction(object):
    def __init__(self, storage=None, **config):
        self.storage = storage

    def connect(self, host='localhost', port=10053):
        try:
            self.storage = Service('storage', host, port)
        except socket.error as err:
            if err.errno == errno.ECONNREFUSED:
                raise ConnectionRefusedError(host, port)
            else:
                raise ConnectionError('Unknown connection error: {0}'.format(err))

    def execute(self):
        raise NotImplementedError()

    def encodeJson(self, filename):
        """
        Tries to read json file with name 'filename' and to encode it with msgpack.

        :param filename: file name that need to be encoded
        :raises IOError: if file does not exists, you have not enough permissions to read it or something else
        :raises CocaineError: if file successfully read but cannot be parsed with json parser
        """
        try:
            with open(filename, 'rb') as fh:
                content = fh.read()
                data = json.loads(content)
                encoded = msgpack.packb(data)
                return encoded
        except IOError as err:
            raise CocaineError('Unable to open file - {0}'.format(err))
        except ValueError as err:
            raise CocaineError('File "{0}" is corrupted - {1}'.format(filename, err))


class ListAction(StorageAction):
    """
    Abstract storage action class which main aim is to provide find list action on 'key' and 'tags'.
    For example if key='manifests' and tags=('apps',) then class will try to find applications list
    """
    def __init__(self, key, tags, storage, **config):
        super(ListAction, self).__init__(storage, **config)
        self.key = key
        self.tags = tags

    def execute(self):
        future = self.storage.find(self.key, self.tags)
        return future


class AppListAction(ListAction):
    def __init__(self, storage, **config):
        super(AppListAction, self).__init__('manifests', APPS_TAGS, storage, **config)


class AppViewAction(StorageAction):
    def __init__(self, storage, **config):
        super(AppViewAction, self).__init__(storage, **config)
        self.name = config.get('name')
        if not self.name:
            raise ValueError('Specify name of application')

    def execute(self):
        future = self.storage.read('manifests', self.name)
        return future


class AppUploadAction(StorageAction):
    """
    Storage action class that tries to upload application into storage asynchronously
    """
    def __init__(self, storage, **config):
        super(AppUploadAction, self).__init__(storage, **config)
        self.name = config.get('name')
        self.manifest = config.get('manifest')
        self.package = config.get('package')
        if not self.name:
            raise ValueError('Please specify name of the app')
        if not self.manifest:
            raise ValueError('Please specify manifest of the app')
        if not self.package:
            raise ValueError('Please specify package of the app')

    def execute(self):
        """
        Encodes manifest and package files and (if successful) uploads them into storage

        :returns: list of two futures on each of them you can bind callback and errorback.
        Doneback is not supported but you can implement own counting cause it is only two futures returned
        """
        manifest = self.encodeJson(self.manifest)
        package = self.encodePackage()
        futures = self.upload(manifest, package)
        return futures

    def encodePackage(self):
        try:
            if not tarfile.is_tarfile(self.package):
                raise CocaineError('File "{0}" is ot tar file'.format(self.package))
            with open(self.package, 'rb') as archive:
                package = msgpack.packb(archive.read())
                return package
        except IOError as err:
            raise CocaineError('Error occurred while reading archive file "{0}" - {1}'.format(self.package, err))

    def upload(self, manifest, package):
        futures = [
            self.storage.write('manifests', self.name, manifest, APPS_TAGS),
            self.storage.write('apps', self.name, package, APPS_TAGS)
        ]
        return futures


class AppRemoveAction(StorageAction):
    """
    Storage action class that removes application 'name' from storage
    """
    def __init__(self, storage, **config):
        super(AppRemoveAction, self).__init__(storage, **config)
        self.name = config.get('name')
        if not self.name:
            raise ValueError('Empty application name')

    def execute(self):
        futures = [
            self.storage.remove("manifests", self.name),
            self.storage.remove("apps", self.name)
        ]
        return futures


class ProfileListAction(ListAction):
    def __init__(self, storage, **config):
        super(ProfileListAction, self).__init__('profiles', PROFILES_TAGS, storage, **config)


def AwaitListWrapper(onChunkReceivedMessage, onErrorMessage=None):
    """
    Simple class decorator that wraps action class with single future returned from execute method and applies callback
    and errorback handlers on execute method.
    Callback simply prints list received and stops event loop.
    Errorback prints error message and stops event loop also.
    """
    def Patch(cls):
        class Wrapper(cls):
            def execute(self):
                future = super(Wrapper, self).execute()
                future.bind(callback=self.onChunkReceived, errorback=self.onErrorReceived)

            def onChunkReceived(self, chunk):
                print(onChunkReceivedMessage)
                for num, profile in enumerate(chunk, start=1):
                    print('\t{0}. {1}'.format(num, profile))
                IOLoop.instance().stop()

            def onErrorReceived(self, exception):
                printError((onErrorMessage or 'Error occurred: {0}').format(exception))
                IOLoop.instance().stop()
        return Wrapper
    return Patch


class SpecificProfileAction(StorageAction):
    def __init__(self, storage, **config):
        super(SpecificProfileAction, self).__init__(storage, **config)
        self.name = config.get('name')
        if not self.name:
            raise ValueError('Please specify profile name')


class ProfileUploadAction(SpecificProfileAction):
    def __init__(self, storage, **config):
        super(ProfileUploadAction, self).__init__(storage, **config)
        self.profile = config.get('manifest')
        if not self.profile:
            raise ValueError('Please specify profile file path')

    def execute(self):
        profile = self.encodeJson(self.profile)
        future = self.storage.write('profiles', self.name, profile, PROFILES_TAGS)
        return future


def AwaitDoneWrapper(onDoneMessage=None, onErrorMessage=None):
    """
    Wrapper class factory for actions with [1; +inf] futures returned from execute method.
    For each future there is bind method invoked with callback, errorback and doneback supplied.
    Event loop stops if all of the chunks received or some error has been thrown
    """
    def Patch(cls):
        class Wrapper(cls):
            def execute(self):
                futures = super(Wrapper, self).execute()
                if not isinstance(futures, collections.Iterable):
                    futures = [futures,]

                self.received = 0
                self.awaits = len(futures)
                for future in futures:
                    future.bind(
                        callback=self.onChunkReceived,
                        errorback=self.onErrorReceived,
                        on_done=self.onChunkReceived
                    )

            def onChunkReceived(self):
                self.received += 1
                if self.received == self.awaits:
                    IOLoop.instance().stop()
                    print((onDoneMessage or 'Action for "{name}" - done').format(name=self.name))

            def onErrorReceived(self, exception):
                printError((onErrorMessage or 'Error occurred on action for "{name}": {error}').format(
                    name=self.name, error=exception)
                )
                IOLoop.instance().stop()
        return Wrapper
    return Patch


class ProfileRemoveAction(SpecificProfileAction):
    def execute(self):
        future = self.storage.remove('profiles', self.name)
        return future


class ProfileViewAction(SpecificProfileAction):
    def execute(self):
        future = self.storage.read('profiles', self.name)
        return future


def AwaitJsonWrapper(onErrorMessage=None):
    def Patch(cls):
        class Wrapper(cls):
            def execute(self):
                future = super(Wrapper, self).execute()
                future.bind(callback=self.onChunkReceived, errorback=self.onErrorReceived)

            def onChunkReceived(self, chunk):
                print(json.dumps(msgpack.unpackb(chunk), indent=4))
                IOLoop.instance().stop()

            def onErrorReceived(self, exception):
                printError((onErrorMessage or 'Unable to view "{name}" - {error}').format(
                    name=self.name, error=exception)
                )
                IOLoop.instance().stop()
        return Wrapper
    return Patch


class RunlistListAction(ListAction):
    def __init__(self, storage, **config):
        super(RunlistListAction, self).__init__('runlists', RUNLISTS_TAGS, storage, **config)


class SpecificRunlistAction(StorageAction):
    def __init__(self, storage, **config):
        super(SpecificRunlistAction, self).__init__(storage, **config)
        self.name = config.get('name')
        if not self.name:
            raise ValueError('Please specify runlist name')


class RunlistViewAction(SpecificRunlistAction):
    def execute(self):
        future = self.storage.read('runlists', self.name)
        return future


class RunlistUploadAction(SpecificRunlistAction):
    def __init__(self, storage, **config):
        super(RunlistUploadAction, self).__init__(storage, **config)
        self.runlist = config.get('manifest')
        self.runlist_raw = config.get('runlist-raw')
        if not any([self.runlist, self.runlist_raw]):
            raise ValueError('Please specify runlist profile file path')

    def execute(self):
        if self.runlist:
            runlist = self.encodeJson(self.runlist)
        else:
            runlist = msgpack.dumps(self.runlist_raw)
        future = self.storage.write('runlists', self.name, runlist, RUNLISTS_TAGS)
        return future


class RunlistRemoveAction(SpecificRunlistAction):
    def execute(self):
        future = self.storage.remove('runlists', self.name)
        return future


class RunlistAddAppAction(SpecificRunlistAction):
    def __init__(self, storage, **config):
        warn('This class is deprecated. You should use "AddApplicationToRunlistAction" instead', DeprecationWarning)
        super(RunlistAddAppAction, self).__init__(storage, **config)
        self.app = config.get('app')
        self.profile = config.get('profile')
        if not self.app:
            raise ValueError('Please specify application name')
        if not self.profile:
            raise ValueError('Please specify profile')

    def execute(self):
        def chain(action):
            class Future(object):
                def __init__(self, future):
                    self.future = future
                    self.future.bind(self.on, self.error)

                def bind(self, callback, errorback, on_done):
                    self.callback = callback
                    self.errorback = errorback
                    self.doneback = on_done

                def on(self, chunk):
                    try:
                        runlist = msgpack.loads(chunk)
                        runlist[action.app] = action.profile
                        uploadRunlistAction = RunlistUploadAction(action.storage, **{
                            'name': action.name,
                            'runlist-raw': runlist
                        })
                        future = uploadRunlistAction.execute()
                        future.bind(self.callback, self.errorback, self.doneback)
                    except Exception as err:
                        self.errorback(err)

                def error(self, error):
                    printError('Runlist location failed - {0}'.format(error))
                    self.errorback()
            return Future

        getRunlistAction = RunlistViewAction(self.storage, **{'name': self.name})
        future = getRunlistAction.execute()
        return chain(self)(future)


class AddApplicationToRunlistAction(SpecificRunlistAction):
    def __init__(self, storage, **config):
        super(AddApplicationToRunlistAction, self).__init__(storage, **config)
        self.app = config.get('app')
        self.profile = config.get('profile')
        if not self.app:
            raise ValueError('Please specify application name')
        if not self.profile:
            raise ValueError('Please specify profile')

    def execute(self):
        chain = ChainFactory().then(self.getRunlist).then(self.parseRunlist).then(self.uploadRunlist)
        return chain

    def getRunlist(self):
        action = RunlistViewAction(self.storage, **{'name': self.name})
        future = action.execute()
        return future

    @chain.synchronous
    def parseRunlist(self, result):
        runlist = msgpack.loads(result.get())
        runlist[self.app] = self.profile
        return runlist

    def uploadRunlist(self, runlist):
        action = RunlistUploadAction(self.storage, **{
            'name': self.name,
            'runlist-raw': runlist.get()
        })
        future = action.execute()
        return future


class ConsoleAddApplicationToRunlistAction(AddApplicationToRunlistAction):
    def execute(self):
        super(ConsoleAddApplicationToRunlistAction, self).execute().then(self.printResult).run()

    def printResult(self, result):
        try:
            MESSAGE = 'Application "{app}" with profile "{profile}" has been successfully added to runlist "{runlist}"'
            print(MESSAGE.format(app=self.app, profile=self.profile, runlist=self.name))
        except Exception as err:
            printError(err)
        finally:
            IOLoop.instance().stop()

class CrashlogListAction(StorageAction):
    def __init__(self, storage, **config):
        super(CrashlogListAction, self).__init__(storage, **config)
        self.name = config.get('name')
        if not self.name:
            raise ValueError('Please specify crashlog name')

    def execute(self):
        future = self.storage.find('crashlogs', (self.name, ))
        return future


def parseCrashlogs(crashlogs, timestamp=None):
    flt = lambda x: (x == timestamp if timestamp else True)
    _list = (log.split(':') for log in crashlogs)
    return [(ts, ctime(float(ts) / 1000000), name) for ts, name in _list if flt(ts)]


class PrettyPrintableCrashlogListAction(CrashlogListAction):
    def execute(self):
        future = super(PrettyPrintableCrashlogListAction, self).execute()
        future.bind(callback=self.onChunkReceived, errorback=self.onErrorReceived)

    def onChunkReceived(self, chunk):
        print("Currently available crashlogs for application '%s'" % self.name)
        for item in parseCrashlogs(chunk):
            print ' '.join(item)
        IOLoop.instance().stop()

    def onErrorReceived(self, exception):
        printError(('' or 'Unable to view "{name}" - {error}').format(name=self.name, error=exception))
        IOLoop.instance().stop()


class CrashlogViewOrRemoveAction(StorageAction):
    def __init__(self, storage, method, **config):
        super(CrashlogViewOrRemoveAction, self).__init__(storage, **config)
        self.name = config.get('name')
        self.timestamp = config.get('manifest')
        self.method = method
        if not self.name:
            raise ValueError('Please specify name')

    def execute(self):
        class Future(object):
            def __init__(self, action, future):
                self.action = action
                self.messagesLeft = 0
                future.bind(self.onChunk, self.onError, self.onDone)

            def bind(self, callback, errorback=None, doneback=None):
                self.callback = callback
                self.errorback = errorback
                self.doneback = doneback

            def onChunk(self, chunk):
                def countable(func):
                    def wrapper(*args, **kwargs):
                        func(*args, **kwargs)
                        self.messagesLeft -= 1
                        if not self.messagesLeft:
                            self.doneback()
                    return wrapper
                crashlogs = parseCrashlogs(chunk, timestamp=self.action.timestamp)
                self.messagesLeft = len(crashlogs)
                if len(crashlogs) == 0:
                    self.doneback()

                for crashlog in crashlogs:
                    key = "%s:%s" % (crashlog[0], crashlog[2])
                    method = getattr(self.action.storage, self.action.method)
                    future = method('crashlogs', key)
                    future.bind(countable(self.callback), countable(self.errorback), self.doneback)

            def onError(self, exception):
                self.errorback(exception)
                self.doneback()

            def onDone(self):
                self.doneback()

        findCrashlogsFuture = self.storage.find('crashlogs', (self.name,))
        readCrashlogFuture = Future(self, findCrashlogsFuture)
        return readCrashlogFuture


class CrashlogViewAction(CrashlogViewOrRemoveAction):
    def __init__(self, storage, **config):
        super(CrashlogViewAction, self).__init__(storage, 'read', **config)


class PrettyPrintableCrashlogViewAction(CrashlogViewAction):
    def execute(self):
        future = super(PrettyPrintableCrashlogViewAction, self).execute()
        future.bind(callback=self.onChunkReceived, errorback=self.onErrorReceived, doneback=IOLoop.instance().stop)

    def onChunkReceived(self, crashlog):
        print('Crashlog:')
        print('\n'.join(msgpack.unpackb(crashlog)))

    def onErrorReceived(self, exception):
        printError(exception)
        IOLoop.instance().stop()


class CrashlogRemoveAction(CrashlogViewOrRemoveAction):
    def __init__(self, storage, **config):
        super(CrashlogRemoveAction, self).__init__(storage, 'remove', **config)


class CrashlogRemoveAllAction(CrashlogViewOrRemoveAction):
    def __init__(self, storage, **config):
        config['manifest'] = None
        super(CrashlogRemoveAllAction, self).__init__(storage, 'remove', **config)


def makePrettyCrashlogRemove(cls, onDoneMessage=None):
    class PrettyWrapper(cls):
        def __init__(self, storage=None, **config):
            super(PrettyWrapper, self).__init__(storage, **config)

        def execute(self):
            future = super(PrettyWrapper, self).execute()
            future.bind(callback=None, errorback=self.onErrorReceived, doneback=self.onDone)

        def onErrorReceived(self, exception):
            printError(exception)
            IOLoop.instance().stop()

        def onDone(self):
            print((onDoneMessage or 'Action for app "{0}" finished').format(self.name))
            IOLoop.instance().stop()
    return PrettyWrapper


APP_LIST_SUCCESS = 'Currently uploaded apps:'
APP_UPLOAD_SUCCESS = 'The app "{name}" has been successfully uploaded'
APP_UPLOAD_FAIL = 'Unable to upload application {name} - {error}'
APP_REMOVE_SUCCESS = 'The app "{name}" has been successfully removed'
APP_REMOVE_FAIL = 'Unable to remove application {name} - {error}'

PROFILE_LIST_SUCCESS = 'Currently uploaded profiles:'
PROFILE_UPLOAD_SUCCESS = 'The profile "{name}" has been successfully uploaded'
PROFILE_UPLOAD_FAIL = 'Unable to upload profile "{name}" - {error}'
PROFILE_REMOVE_SUCCESS = 'The profile "{name}" has been successfully removed'
PROFILE_REMOVE_FAIL = 'Unable to remove profile "{name}" - {error}'

RUNLIST_LIST_SUCCESS = 'Currently uploaded runlists:'
RUNLIST_UPLOAD_SUCCESS = 'The runlist "{name}" has been successfully uploaded'
RUNLIST_UPLOAD_FAIL = 'Unable to upload runlist "{name}" - {error}'
RUNLIST_REMOVE_SUCCESS = 'The runlist "{name}" has been successfully removed'
RUNLIST_REMOVE_FAIL = 'Unable to remove runlist "{name}" - {error}'

CRASHLOG_REMOVE_SUCCESS = 'Crashlog for app "{0}" have been removed'
CRASHLOGS_REMOVE_SUCCESS = 'Crashlogs for app "{0}" have been removed'

AVAILABLE_TOOLS_ACTIONS = {
    'app:list': AwaitListWrapper(APP_LIST_SUCCESS)(AppListAction),
    'app:view': AwaitJsonWrapper()(AppViewAction),
    'app:upload': AwaitDoneWrapper(APP_UPLOAD_SUCCESS, APP_UPLOAD_FAIL)(AppUploadAction),
    'app:remove': AwaitDoneWrapper(APP_REMOVE_SUCCESS, APP_REMOVE_FAIL)(AppRemoveAction),
    'profile:list': AwaitListWrapper(PROFILE_LIST_SUCCESS)(ProfileListAction),
    'profile:view': AwaitJsonWrapper()(ProfileViewAction),
    'profile:upload': AwaitDoneWrapper(PROFILE_UPLOAD_SUCCESS, PROFILE_UPLOAD_FAIL)(ProfileUploadAction),
    'profile:remove': AwaitDoneWrapper(PROFILE_REMOVE_SUCCESS, PROFILE_REMOVE_FAIL)(ProfileRemoveAction),
    'runlist:list': AwaitListWrapper(RUNLIST_LIST_SUCCESS)(RunlistListAction),
    'runlist:view': AwaitJsonWrapper()(RunlistViewAction),
    'runlist:upload': AwaitDoneWrapper(RUNLIST_UPLOAD_SUCCESS, RUNLIST_UPLOAD_FAIL)(RunlistUploadAction),
    'runlist:remove': AwaitDoneWrapper(RUNLIST_REMOVE_SUCCESS, RUNLIST_REMOVE_FAIL)(RunlistRemoveAction),
    'runlist:add-app': ConsoleAddApplicationToRunlistAction,
    'crashlog:list': PrettyPrintableCrashlogListAction,
    'crashlog:view': PrettyPrintableCrashlogViewAction,
    'crashlog:remove': makePrettyCrashlogRemove(CrashlogRemoveAction, CRASHLOG_REMOVE_SUCCESS),
    'crashlog:removeall': makePrettyCrashlogRemove(CrashlogRemoveAllAction, CRASHLOGS_REMOVE_SUCCESS)
}


class NodeAction(object):
    def __init__(self, node=None, **config):
        self.node = node

    def execute(self):
        raise NotImplementedError()


class NodeInfoAction(NodeAction):
    def execute(self):
        future = self.node.info()
        return future


class AppStartAction(NodeAction):
    def __init__(self, node, **config):
        super(AppStartAction, self).__init__(node, **config)
        self.name = config.get('name')
        self.profile = config.get('profile')
        if not self.name:
            raise ValueError('Please specify application name')
        if not self.profile:
            raise ValueError('Please specify profile name')

    def execute(self):
        apps = {
            self.name: self.profile
        }
        future = self.node.start_app(apps)
        return future


class AppPauseAction(NodeAction):
    def __init__(self, node, **config):
        super(AppPauseAction, self).__init__(node, **config)
        self.name = config.get('name')
        if not self.name:
            raise ValueError('Please specify application name')

    def execute(self):
        future = self.node.pause_app([self.name])
        return future


def NodeActionPrettyWrapper():
    def Patch(cls):
        class Wrapper(cls):
            def execute(self):
                future = super(Wrapper, self).execute()
                future.bind(callback=self.onChunkReceived, errorback=self.onErrorReceived)

            def onChunkReceived(self, chunk):
                print(json.dumps(chunk, indent=4))
                IOLoop.instance().stop()

            def onErrorReceived(self, exception):
                printError('Error occurred: {what}'.format(what=exception))
                IOLoop.instance().stop()
        return Wrapper
    return Patch


class AppCheckAction(NodeAction):
    def __init__(self, node, **config):
        super(AppCheckAction, self).__init__(node, **config)
        self.name = config.get('name')
        if not self.name:
            raise ValueError('Please specify application name')

    def execute(self):
        class Future(object):
            def __init__(self, action, future):
                self.action = action
                self.messagesLeft = 0
                future.bind(self.onChunk, self.onError)

            def bind(self, callback, errorback=None):
                self.callback = callback
                self.errorback = errorback

            def onChunk(self, chunk):
                state = 'stopped or missing'
                try:
                    apps = chunk['apps']
                    app = apps[self.action.name]
                    state = app['state']
                except KeyError:
                    pass
                finally:
                    self.callback({self.action.name: state})

            def onError(self, exception):
                self.errorback(exception)

        future = self.node.info()
        parseInfoFuture = Future(self, future)
        return parseInfoFuture


class PrettyPrintableAppCheckAction(AppCheckAction):
    def execute(self):
        future = super(PrettyPrintableAppCheckAction, self).execute()
        future.bind(callback=self.onChunkReceived, errorback=self.onErrorReceived)

    def onChunkReceived(self, chunk):
        app = self.name
        state = chunk[app]
        print('{0}: {1}'.format(app, state))
        IOLoop.instance().stop()
        if 'running' not in state:
            exit(1)

    def onErrorReceived(self, exception):
        printError('Error occurred: {what}'.format(what=exception))
        IOLoop.instance().stop()
        exit(1)

AVAILABLE_NODE_ACTIONS = {
    'info': NodeActionPrettyWrapper()(NodeInfoAction),
    'app:start': NodeActionPrettyWrapper()(AppStartAction),
    'app:pause': NodeActionPrettyWrapper()(AppPauseAction),
    'app:check': PrettyPrintableAppCheckAction
}


class ToolsError(Exception):
    pass


class Executor(object):
    """
    This class represents abstract action executor for specified service 'serviceName' and actions pool
    """
    def __init__(self, serviceName, availableActions):
        self.serviceName = serviceName
        self.availableActions = availableActions
        self.loop = IOLoop.instance()

    def executeAction(self, actionName, **options):
        """
        Tries to create service 'serviceName' gets selected action and (if success) invokes it. If any error is
        occurred, it will be immediately printed to stderr and application exits with return code 1

        :param actionName: action name that must be available for selected service
        :param options: various action configuration
        """
        try:
            service = self.createService(options.get('host'), options.get('port'))

            Action = self.availableActions[actionName]
            action = Action(service, **options)
            action.execute()
            self.loop.add_timeout(time() + options.get('timeout', 1.0), self.timeoutErrorback)
            IOLoop.instance().start()
        except CocaineError as err:
            raise ToolsError(err)
        except ValueError as err:
            raise ToolsError(err)
        except KeyError as err:
            raise ToolsError('Action {0} is not available'.format(err))
        except Exception as err:
            raise ToolsError('Unknown error occurred - {0}'.format(err))

    def createService(self, host, port):
        try:
            service = Service(self.serviceName, host, port)
            return service
        except socket.error as err:
            if err.errno == errno.ECONNREFUSED:
                raise ConnectionRefusedError(host, port)
            else:
                raise ConnectionError('Unknown connection error: {0}'.format(err))

    def timeoutErrorback(self):
        printError('Timeout')
        self.loop.stop()


class ToolsExecutor(Executor):
    def __init__(self):
        super(ToolsExecutor, self).__init__('storage', AVAILABLE_TOOLS_ACTIONS)


class NodeExecutor(Executor):
    def __init__(self):
        super(NodeExecutor, self).__init__('node', AVAILABLE_NODE_ACTIONS)
