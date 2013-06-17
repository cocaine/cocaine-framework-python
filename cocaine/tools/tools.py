import json
import socket
import errno
import tarfile
from time import ctime
from cocaine.futures.chain import ChainFactory

from cocaine.services import Service
import msgpack

from cocaine.exceptions import ConnectionRefusedError, ConnectionError
from cocaine.exceptions import CocaineError


APPS_TAGS = ("app",)
RUNLISTS_TAGS = ("runlist",)
PROFILES_TAGS = ("profile",)


class ToolsError(Exception):
    pass


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
        return self.storage.find(self.key, self.tags)


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
        return self.storage.read('manifests', self.name)


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
        """
        return ChainFactory().then(self.do)

    def do(self):
        manifest = self.encodeJson(self.manifest)
        package = self.encodePackage()
        manifestStatus = yield self.storage.write('manifests', self.name, manifest, APPS_TAGS)
        appsStatus = yield self.storage.write('apps', self.name, package, APPS_TAGS)
        #yield [manifestStatus, appsStatus]

    def encodePackage(self):
        try:
            if not tarfile.is_tarfile(self.package):
                raise CocaineError('File "{0}" is ot tar file'.format(self.package))
            with open(self.package, 'rb') as archive:
                package = msgpack.packb(archive.read())
                return package
        except IOError as err:
            raise CocaineError('Error occurred while reading archive file "{0}" - {1}'.format(self.package, err))


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
        return ChainFactory([self.do])

    def do(self):
        yield self.storage.remove("manifests", self.name)
        yield self.storage.remove("apps", self.name)


class ProfileListAction(ListAction):
    def __init__(self, storage, **config):
        super(ProfileListAction, self).__init__('profiles', PROFILES_TAGS, storage, **config)


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
        return self.storage.write('profiles', self.name, profile, PROFILES_TAGS)


class ProfileRemoveAction(SpecificProfileAction):
    def execute(self):
        return self.storage.remove('profiles', self.name)


class ProfileViewAction(SpecificProfileAction):
    def execute(self):
        return self.storage.read('profiles', self.name)


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
        return self.storage.read('runlists', self.name)


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
        return self.storage.write('runlists', self.name, runlist, RUNLISTS_TAGS)


class RunlistRemoveAction(SpecificRunlistAction):
    def execute(self):
        future = self.storage.remove('runlists', self.name)
        return future


class RunlistAddApplicationAction(SpecificRunlistAction):
    def __init__(self, storage, **config):
        super(RunlistAddApplicationAction, self).__init__(storage, **config)
        self.app = config.get('app')
        self.profile = config.get('profile')
        if not self.app:
            raise ValueError('Please specify application name')
        if not self.profile:
            raise ValueError('Please specify profile')

    def execute(self):
        return ChainFactory([self.do])

    def do(self):
        runlistInfo = yield RunlistViewAction(self.storage, **{'name': self.name}).execute()
        runlist = msgpack.loads(runlistInfo)
        runlist[self.app] = self.profile
        action = RunlistUploadAction(self.storage, **{
            'name': self.name,
            'runlist-raw': runlist
        })
        status = yield action.execute()
        yield status


class CrashlogListAction(StorageAction):
    def __init__(self, storage, **config):
        super(CrashlogListAction, self).__init__(storage, **config)
        self.name = config.get('name')
        if not self.name:
            raise ValueError('Please specify crashlog name')

    def execute(self):
        return self.storage.find('crashlogs', (self.name, ))


def parseCrashlogs(crashlogs, timestamp=None):
    flt = lambda x: (x == timestamp if timestamp else True)
    _list = (log.split(':') for log in crashlogs)
    return [(ts, ctime(float(ts) / 1000000), name) for ts, name in _list if flt(ts)]


class CrashlogAction(StorageAction):
    def __init__(self, storage, **config):
        super(CrashlogAction, self).__init__(storage, **config)
        self.name = config.get('name')
        self.timestamp = config.get('manifest')
        if not self.name:
            raise ValueError('Please specify name')


class CrashlogViewAction(CrashlogAction):
    def __init__(self, storage, **config):
        super(CrashlogViewAction, self).__init__(storage, **config)

    def execute(self):
        return ChainFactory([self.do])

    def do(self):
        crashlogs = yield self.storage.find('crashlogs', (self.name,))
        yield # get choke
        parsedCrashlogs = parseCrashlogs(crashlogs, timestamp=self.timestamp)
        contents = []
        for crashlog in parsedCrashlogs:
            key = '%s:%s' % (crashlog[0], crashlog[2])
            content = yield self.storage.read('crashlogs', key)
            yield # get choke
            contents.append(content)
        yield ''.join(contents)


class CrashlogRemoveAction(CrashlogAction):
    def __init__(self, storage, **config):
        super(CrashlogRemoveAction, self).__init__(storage, **config)

    def execute(self):
        return ChainFactory([self.do])

    def do(self):
        crashlogs = yield self.storage.find('crashlogs', (self.name,))
        yield # get choke
        parsedCrashlogs = parseCrashlogs(crashlogs, timestamp=self.timestamp)
        for crashlog in parsedCrashlogs:
            key = '%s:%s' % (crashlog[0], crashlog[2])
            yield self.storage.remove('crashlogs', key)


class CrashlogRemoveAllAction(CrashlogRemoveAction):
    def __init__(self, storage, **config):
        config['manifest'] = None
        super(CrashlogRemoveAllAction, self).__init__(storage, 'remove', **config)


class NodeAction(object):
    def __init__(self, node=None, **config):
        self.node = node
        self.config = config

    def execute(self):
        raise NotImplementedError()


class NodeInfoAction(NodeAction):
    def execute(self):
        return self.node.info()


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
        return self.node.start_app(apps)


class AppPauseAction(NodeAction):
    def __init__(self, node, **config):
        super(AppPauseAction, self).__init__(node, **config)
        self.name = config.get('name')
        if not self.name:
            raise ValueError('Please specify application name')

    def execute(self):
        future = self.node.pause_app([self.name])
        return future


class AppRestartAction(NodeAction):
    def __init__(self, node, **config):
        super(AppRestartAction, self).__init__(node, **config)
        self.name = config.get('name')
        self.profile = config.get('profile')
        if not self.name:
            raise ValueError('Please specify application name')

    def execute(self):
        return ChainFactory().then(self.doAction)

    def doAction(self):
        try:
            info = yield NodeInfoAction(self.node, **self.config).execute()
            profile = self.profile or info['apps'][self.name]['profile']
            appStopStatus = yield AppPauseAction(self.node, **self.config).execute()
            appStartConfig = {
                'host': self.config['host'],
                'port': self.config['port'],
                'name': self.name,
                'profile': profile
            }
            appStartStatus = yield AppStartAction(self.node, **appStartConfig).execute()
            yield [appStopStatus, appStartStatus]
        except KeyError:
            raise ToolsError('Application "{0}" is not running and profile not specified'.format(self.name))
        except Exception as err:
            raise ToolsError('Unknown error - {0}'.format(err))


class AppCheckAction(NodeAction):
    def __init__(self, node, **config):
        super(AppCheckAction, self).__init__(node, **config)
        self.name = config.get('name')
        if not self.name:
            raise ValueError('Please specify application name')

    def execute(self):
        return self.node.info().then(self.parseInfo)

    def parseInfo(self, result):
        state = 'stopped or missing'
        try:
            info = result.get()
            apps = info['apps']
            app = apps[self.name]
            state = app['state']
        except KeyError:
            pass
        return {self.name: state}