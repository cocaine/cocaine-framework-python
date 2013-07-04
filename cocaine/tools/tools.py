import ast
import json
import os
import re
import socket
import errno
import tarfile
import tempfile
import time
import msgpack

from cocaine.futures import chain
from cocaine.futures.chain import Chain
from cocaine.services import Service
from cocaine.exceptions import CocaineError, ConnectionRefusedError, ConnectionError, ServiceError
from cocaine.tools.repository import GitRepositoryDownloader, RepositoryDownloadError
from cocaine.tools.installer import PythonModuleInstaller, ModuleInstallError


__all__ = [
    'APPS_TAGS',
    'RUNLISTS_TAGS',
    'PROFILES_TAGS',
    'parseCrashlogs',

    'ToolsError',
    'ServiceCallError',

    'NodeInfoAction',
    'CallAction',

    'AppListAction',
    'AppViewAction',
    'AppUploadAction',
    'AppRemoveAction',
    'AppStartAction',
    'AppPauseAction',
    'AppRestartAction',
    'AppCheckAction',
    'AppUploadFromRepositoryAction',

    'ProfileListAction',
    'ProfileViewAction',
    'ProfileUploadAction',
    'ProfileRemoveAction',

    'RunlistListAction',
    'RunlistViewAction',
    'RunlistUploadAction',
    'RunlistRemoveAction',
    'RunlistAddApplicationAction',

    'CrashlogListAction',
    'CrashlogViewAction',
    'CrashlogRemoveAction',
    'CrashlogRemoveAllAction',
]


APPS_TAGS = ('app',)
RUNLISTS_TAGS = ('runlist',)
PROFILES_TAGS = ('profile',)


class ToolsError(CocaineError):
    pass


class UploadError(ToolsError):
    pass


class ServiceCallError(ToolsError):
    def __init__(self, serviceName, reason):
        self.message = 'Error in service "{0}" - {1}'.format(serviceName, reason)

    def __str__(self):
        return self.message


class JsonEncoder(object):
    def encode(self, filename):
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


class PackageEncoder(object):
    def encode(self, filename):
        try:
            if not tarfile.is_tarfile(filename):
                raise CocaineError('File "{0}" is ot tar file'.format(filename))
            with open(filename, 'rb') as archive:
                package = msgpack.packb(archive.read())
                return package
        except IOError as err:
            raise CocaineError('Error occurred while reading archive file "{0}" - {1}'.format(filename, err))


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


class ListAction(StorageAction):
    """
    Abstract storage action class which main aim is to provide find list action on 'key' and 'tags'.
    For example if key='manifests' and tags=('apps',) this class will try to find applications list
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
        self.jsonEncoder = JsonEncoder()
        self.packageEncoder = PackageEncoder()
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
        return Chain().then(self.do)

    def do(self):
        manifest = self.jsonEncoder.encode(self.manifest)
        package = self.packageEncoder.encode(self.package)
        yield self.storage.write('manifests', self.name, manifest, APPS_TAGS)
        yield self.storage.write('apps', self.name, package, APPS_TAGS)
        yield 'Done'


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
        return Chain([self.do])

    def do(self):
        yield self.storage.remove('manifests', self.name)
        yield self.storage.remove('apps', self.name)
        yield 'Done'


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
        self.jsonEncoder = JsonEncoder()
        if not self.profile:
            raise ValueError('Please specify profile file path')

    def execute(self):
        profile = self.jsonEncoder.encode(self.profile)
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
        self.jsonEncoder = JsonEncoder()
        if not any([self.runlist, self.runlist_raw]):
            raise ValueError('Please specify runlist file path')

    def execute(self):
        if self.runlist:
            runlist = self.jsonEncoder.encode(self.runlist)
        else:
            runlist = msgpack.dumps(self.runlist_raw)
        return self.storage.write('runlists', self.name, runlist, RUNLISTS_TAGS)


class RunlistRemoveAction(SpecificRunlistAction):
    def execute(self):
        return self.storage.remove('runlists', self.name)


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
        return Chain([self.do])

    def do(self):
        runlistInfo = yield RunlistViewAction(self.storage, **{'name': self.name}).execute()
        runlist = msgpack.loads(runlistInfo)
        runlist[self.app] = self.profile
        runlistUploadAction = RunlistUploadAction(self.storage, **{
            'name': self.name,
            'runlist-raw': runlist
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
    _list = (log.split(':', 1) for log in crashlogs)
    return [(ts, time.ctime(float(ts) / 1000000), name) for ts, name in _list if flt(ts)]


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
        return Chain([self.do])

    def do(self):
        crashlogs = yield self.storage.find('crashlogs', (self.name,))
        parsedCrashlogs = parseCrashlogs(crashlogs, timestamp=self.timestamp)
        contents = []
        for crashlog in parsedCrashlogs:
            key = '%s:%s' % (crashlog[0], crashlog[2])
            content = yield self.storage.read('crashlogs', key)
            contents.append(content)
        yield ''.join(contents)


class CrashlogRemoveAction(CrashlogAction):
    def __init__(self, storage, **config):
        super(CrashlogRemoveAction, self).__init__(storage, **config)

    def execute(self):
        return Chain([self.do])

    def do(self):
        crashlogs = yield self.storage.find('crashlogs', (self.name,))
        parsedCrashlogs = parseCrashlogs(crashlogs, timestamp=self.timestamp)
        for crashlog in parsedCrashlogs:
            key = '%s:%s' % (crashlog[0], crashlog[2])
            yield self.storage.remove('crashlogs', key)
        yield 'Done'


class CrashlogRemoveAllAction(CrashlogRemoveAction):
    def __init__(self, storage, **config):
        config['manifest'] = None
        super(CrashlogRemoveAllAction, self).__init__(storage, **config)


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
        return Chain([self.doAction])

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
        return Chain([self.do])

    def do(self):
        state = 'stopped or missing'
        try:
            info = yield self.node.info()
            apps = info['apps']
            app = apps[self.name]
            state = app['state']
        except KeyError:
            pass
        yield {self.name: state}


class AppUploadFromRepositoryAction(StorageAction):
    def __init__(self, storage, **config):
        super(AppUploadFromRepositoryAction, self).__init__(storage, **config)
        self.name = config.get('name')
        self.url = config.get('url')
        if not self.url:
            raise ValueError('Please specify repository URL')
        if not self.name:
            rx = re.compile(r'^.*/(?P<name>.*?)(\..*)?$')
            match = rx.match(self.url)
            self.name = match.group('name')

    def execute(self):
        return Chain([self.doWork])

    def doWork(self):
        repositoryPath = tempfile.mkdtemp()
        manifestPath = os.path.join(repositoryPath, 'manifest-start.json')
        packagePath = os.path.join(repositoryPath, 'package.tar.gz')
        self.repositoryDownloader = GitRepositoryDownloader()
        self.moduleInstaller = PythonModuleInstaller(repositoryPath, manifestPath)
        print('Repository path: {0}'.format(repositoryPath))
        try:
            yield self.cloneRepository(repositoryPath)
            yield self.installRepository()
            yield self.createPackage(repositoryPath, packagePath)
            yield AppUploadAction(self.storage, **{
                'name': self.name,
                'manifest': manifestPath,
                'package': packagePath
            }).execute()
        except (RepositoryDownloadError, ModuleInstallError) as err:
            print(err)

    @chain.concurrent
    def cloneRepository(self, repositoryPath):
        self.repositoryDownloader.download(self.url, repositoryPath)

    @chain.concurrent
    def installRepository(self):
        self.moduleInstaller.install()

    @chain.concurrent
    def createPackage(self, repositoryPath, packagePath):
        with tarfile.open(packagePath, mode='w:gz') as tar:
            tar.add(repositoryPath, arcname='')


class CallAction(NodeAction):
    def __init__(self, node, **config):
        super(CallAction, self).__init__(node, **config)
        command = config.get('command')
        if not command:
            raise ValueError('Please specify service name for getting API or full command to invoke')
        service, separator, methodWithArguments = command.partition('.')
        self.serviceName = service
        rx = re.compile(r'(.*?)\((.*)\)')
        match = rx.match(methodWithArguments)
        if match:
            self.methodName, self.args = match.groups()
        else:
            self.methodName = methodWithArguments

    def execute(self):
        return Chain([self.callService])

    def callService(self):
        service = self.getService()
        response = {
            'service': self.serviceName,
        }
        if not self.methodName:
            api = service._service_api
            response['request'] = 'api'
            response['response'] = api
        else:
            method = self.getMethod(service)
            args = self.parseArguments()
            result = yield method(*args)
            response['request'] = 'invoke'
            response['response'] = result
        yield response

    def getService(self):
        try:
            service = Service(self.serviceName)
            return service
        except Exception as err:
            raise ServiceCallError(self.serviceName, err)

    def getMethod(self, service):
        try:
            method = service.__getattribute__(self.methodName)
            return method
        except AttributeError:
            raise ServiceError(self.serviceName, 'method "{0}" is not found'.format(self.methodName), 1)

    def parseArguments(self):
        if not self.args:
            return ()

        try:
            args = ast.literal_eval(self.args)
            if not isinstance(args, tuple):
                args = (args,)
            return args
        except (SyntaxError, ValueError) as err:
            raise ServiceCallError(self.serviceName, err)
        except Exception as err:
            print(err, type(err))
