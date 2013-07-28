import logging
import os
import re
import shutil
import tarfile
import tempfile
import msgpack

from cocaine.exceptions import ToolsError
from cocaine.futures import chain
from cocaine.futures.chain import Chain
from cocaine.tools import actions, log
from cocaine.tools.actions import common
from cocaine.tools.installer import PythonModuleInstaller, ModuleInstallError, _locateFile
from cocaine.tools.repository import GitRepositoryDownloader, RepositoryDownloadError
from cocaine.tools.encoders import JsonEncoder, PackageEncoder
from cocaine.tools.tags import APPS_TAGS

__author__ = 'Evgeny Safronov <division494@gmail.com>'

WRONG_APPLICATION_NAME = 'Application "{0}" is not valid application'

venvFactory = {
    'None': None,
    'P': PythonModuleInstaller,
    'R': None,
    'J': None
}


class List(actions.List):
    def __init__(self, storage, **config):
        super(List, self).__init__('manifests', APPS_TAGS, storage, **config)


class View(actions.Storage):
    def __init__(self, storage, **config):
        super(View, self).__init__(storage, **config)
        self.name = config.get('name')
        if not self.name:
            raise ValueError('Specify name of application')

    def execute(self):
        return self.storage.read('manifests', self.name)


class Upload(actions.Storage):
    """
    Storage action class that tries to upload application into storage asynchronously
    """

    def __init__(self, storage, **config):
        super(Upload, self).__init__(storage, **config)
        self.name = config.get('name')
        self.manifest = config.get('manifest')
        self.manifestRaw = config.get('manifest-raw')
        self.package = config.get('package')
        self.jsonEncoder = JsonEncoder()
        self.packageEncoder = PackageEncoder()

        if not self.name:
            raise ValueError('Please specify name of the app')
        if not any([self.manifest, self.manifestRaw]):
            raise ValueError('Please specify manifest of the app')
        if not self.package:
            raise ValueError('Please specify package of the app')

    def execute(self):
        """
        Encodes manifest and package files and (if successful) uploads them into storage
        """
        return Chain([self.do])

    def do(self):
        if self.manifest:
            manifest = self.jsonEncoder.encode(self.manifest)
        else:
            manifest = msgpack.dumps(self.manifestRaw)
        package = self.packageEncoder.encode(self.package)
        yield self.storage.write('manifests', self.name, manifest, APPS_TAGS)
        yield self.storage.write('apps', self.name, package, APPS_TAGS)
        yield 'Done'


class Remove(actions.Storage):
    """
    Storage action class that removes application 'name' from storage
    """

    def __init__(self, storage, **config):
        super(Remove, self).__init__(storage, **config)
        self.name = config.get('name')
        if not self.name:
            raise ValueError('Empty application name')

    def execute(self):
        return Chain([self.do])

    def do(self):
        yield self.storage.remove('manifests', self.name)
        yield self.storage.remove('apps', self.name)
        yield 'Done'


class Start(common.Node):
    def __init__(self, node, **config):
        super(Start, self).__init__(node, **config)
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


class Stop(common.Node):
    def __init__(self, node, **config):
        super(Stop, self).__init__(node, **config)
        self.name = config.get('name')
        if not self.name:
            raise ValueError('Please specify application name')

    def execute(self):
        future = self.node.pause_app([self.name])
        return future


class Restart(common.Node):
    def __init__(self, node, **config):
        super(Restart, self).__init__(node, **config)
        self.name = config.get('name')
        self.profile = config.get('profile')
        if not self.name:
            raise ValueError('Please specify application name')

    def execute(self):
        return Chain([self.doAction])

    def doAction(self):
        try:
            info = yield common.NodeInfo(self.node, **self.config).execute()
            profile = self.profile or info['apps'][self.name]['profile']
            appStopStatus = yield Stop(self.node, **self.config).execute()
            appStartConfig = {
                'host': self.config['host'],
                'port': self.config['port'],
                'name': self.name,
                'profile': profile
            }
            appStartStatus = yield Start(self.node, **appStartConfig).execute()
            yield [appStopStatus, appStartStatus]
        except KeyError:
            raise ToolsError('Application "{0}" is not running and profile not specified'.format(self.name))
        except Exception as err:
            raise ToolsError('Unknown error - {0}'.format(err))


class Check(common.Node):
    def __init__(self, node, **config):
        super(Check, self).__init__(node, **config)
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


class LocalUpload(actions.Storage):
    def __init__(self, storage, **config):
        super(LocalUpload, self).__init__(storage, **config)
        self.path = config.get('path') or os.path.curdir
        self.name = config.get('name')
        self.manifest = config.get('manifest')
        self.virtualEnvironmentType = config.get('venv')
        if not self.name:
            self.name = os.path.basename(os.path.abspath(self.path))
        if not self.name:
            raise ValueError(WRONG_APPLICATION_NAME.format(self.name))

    def execute(self):
        return Chain([self.doWork])

    def doWork(self):
        try:
            repositoryPath = self._createRepository()
            manifestPath = self.manifest or _locateFile(self.path, 'manifest.json')
            Installer = venvFactory[self.virtualEnvironmentType]
            if Installer:
                yield self._createVirtualEnvironment(repositoryPath, manifestPath, Installer)
                manifestPath = os.path.join(repositoryPath, 'manifest.json')
            else:
                pass

            packagePath = self._createPackage(repositoryPath)
            yield Upload(self.storage, **{
                'name': self.name,
                'manifest': manifestPath,
                'package': packagePath
            }).execute()
            yield 'Application {0} has been successfully uploaded'.format(self.name)
        except (RepositoryDownloadError, ModuleInstallError) as err:
            print(err)

    def _createRepository(self):
        repositoryPath = tempfile.mkdtemp()
        repositoryPath = os.path.join(repositoryPath, 'repo')
        log.debug('Repository temporary path - "{0}"'.format(repositoryPath))
        shutil.copytree(self.path, repositoryPath)
        return repositoryPath

    @chain.concurrent
    def _createVirtualEnvironment(self, repositoryPath, manifestPath, Installer):
        log.debug('Creating virtual environment "{0}" ...'.format(self.virtualEnvironmentType))
        stream = None
        for handler in log.handlers:
            if isinstance(handler, logging.StreamHandler) and hasattr(handler, 'fileno'):
                stream = handler.stream
                break
        installer = Installer(path=repositoryPath, outputPath=repositoryPath, manifestPath=manifestPath, stream=stream)
        installer.install()

    def _createPackage(self, repositoryPath):
        log.debug('Creating package')
        packagePath = os.path.join(repositoryPath, 'package.tar.gz')
        tar = tarfile.open(packagePath, mode='w:gz')
        tar.add(repositoryPath, arcname='')
        tar.close()
        return packagePath


class UploadRemote(actions.Storage):
    def __init__(self, storage, **config):
        super(UploadRemote, self).__init__(storage, **config)
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
            yield Upload(self.storage, **{
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
        tar = tarfile.open(packagePath, mode='w:gz')
        tar.add(repositoryPath, arcname='')