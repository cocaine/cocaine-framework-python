import logging
import os
import re
import shutil
import tarfile
import tempfile
import msgpack

from cocaine.exceptions import ToolsError
from cocaine.futures import chain
from cocaine.tools import actions, log
from cocaine.tools.actions import common, readArchive, CocaineConfigReader
from cocaine.tools.actions.common import NodeInfo
from cocaine.tools.installer import PythonModuleInstaller, ModuleInstallError, _locateFile
from cocaine.tools.repository import GitRepositoryDownloader, RepositoryDownloadError
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
    def __init__(self, storage):
        super(List, self).__init__('manifests', APPS_TAGS, storage)


class View(actions.Storage):
    def __init__(self, storage, name):
        super(View, self).__init__(storage)
        self.name = name
        if not self.name:
            raise ValueError('Specify name of the application')

    def execute(self):
        return self.storage.read('manifests', self.name)


class Upload(actions.Storage):
    """
    Storage action class that tries to upload application into storage asynchronously
    """

    def __init__(self, storage, name, manifest, package):
        super(Upload, self).__init__(storage)
        self.name = name
        self.manifest = manifest
        self.package = package

        if not self.name:
            raise ValueError('Please specify name of the app')
        if not self.manifest:
            raise ValueError('Please specify manifest of the app')
        if not self.package:
            raise ValueError('Please specify package of the app')

    @chain.source
    def execute(self):
        """
        Encodes manifest and package files and (if successful) uploads them into storage
        """
        log.info('Uploading "%s"... ', self.name)
        manifest = CocaineConfigReader.load(self.manifest)
        package = msgpack.dumps(readArchive(self.package))
        yield self.storage.write('manifests', self.name, manifest, APPS_TAGS)
        yield self.storage.write('apps', self.name, package, APPS_TAGS)
        log.info('OK')


class Remove(actions.Storage):
    """
    Storage action class that removes application 'name' from storage
    """

    def __init__(self, storage, name):
        super(Remove, self).__init__(storage)
        self.name = name
        if not self.name:
            raise ValueError('Empty application name')

    @chain.source
    def execute(self):
        log.info('Removing "%s"... ', self.name)
        apps = yield List(self.storage).execute()
        if self.name not in apps:
            raise ToolsError('application "{0}" does not exist'.format(self.name))
        yield self.storage.remove('manifests', self.name)
        yield self.storage.remove('apps', self.name)
        log.info('OK')


class Start(common.Node):
    def __init__(self, node, name, profile):
        super(Start, self).__init__(node)
        self.name = name
        self.profile = profile
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
    def __init__(self, node, name):
        super(Stop, self).__init__(node)
        self.name = name
        if not self.name:
            raise ValueError('Please specify application name')

    def execute(self):
        return self.node.pause_app([self.name])


class Restart(common.Node):
    def __init__(self, node, locator, name, profile):
        super(Restart, self).__init__(node)
        self.locator = locator
        self.name = name
        self.profile = profile
        if not self.name:
            raise ValueError('Please specify application name')

    @chain.source
    def execute(self):
        try:
            info = yield NodeInfo(self.node, self.locator).execute()
            profile = self.profile or info['apps'][self.name]['profile']
            appStopStatus = yield Stop(self.node, name=self.name).execute()
            appStartStatus = yield Start(self.node, name=self.name, profile=profile).execute()
            yield [appStopStatus, appStartStatus]
        except KeyError:
            raise ToolsError('Application "{0}" is not running and profile not specified'.format(self.name))
        except Exception as err:
            raise ToolsError('Unknown error - {0}'.format(err))


class Check(common.Node):
    def __init__(self, node, locator, name):
        super(Check, self).__init__(node)
        self.name = name
        self.locator = locator
        if not self.name:
            raise ValueError('Please specify application name')

    @chain.source
    def execute(self):
        state = 'stopped or missing'
        try:
            info = yield NodeInfo(self.node, self.locator).execute()
            apps = info['apps']
            app = apps[self.name]
            state = app['state']
        except KeyError:
            pass
        yield {self.name: state}


class LocalUpload(actions.Storage):
    def __init__(self, storage, path, name, manifest, venv):
        super(LocalUpload, self).__init__(storage)
        self.path = path or os.path.curdir
        self.name = name
        self.manifest = manifest
        self.virtualEnvironmentType = venv
        if not self.name:
            self.name = os.path.basename(os.path.abspath(self.path))
        if not self.name:
            raise ValueError(WRONG_APPLICATION_NAME.format(self.name))

    @chain.source
    def execute(self):
        try:
            repositoryPath = self._createRepository()
            if self.manifest:
                manifestPath = self.manifest
            else:
                log.info('Locating manifest... ')
                manifestPath = _locateFile(self.path, 'manifest.json')
                log.info('OK - %s', manifestPath)
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
        except (RepositoryDownloadError, ModuleInstallError) as err:
            log.error(err)

    def _createRepository(self):
        repositoryPath = tempfile.mkdtemp()
        repositoryPath = os.path.join(repositoryPath, 'repo')
        log.debug('Repository temporary path - "{0}"'.format(repositoryPath))
        shutil.copytree(self.path, repositoryPath)
        return repositoryPath

    @chain.concurrent
    def _createVirtualEnvironment(self, repositoryPath, manifestPath, Installer):
        log.debug('Creating virtual environment "{0}"...'.format(self.virtualEnvironmentType))
        stream = None
        for handler in log.handlers:
            if isinstance(handler, logging.StreamHandler) and hasattr(handler, 'fileno'):
                stream = handler.stream
                break
        installer = Installer(path=repositoryPath, outputPath=repositoryPath, manifestPath=manifestPath, stream=stream)
        installer.install()

    def _createPackage(self, repositoryPath):
        log.info('Creating package... ')
        packagePath = os.path.join(repositoryPath, 'package.tar.gz')
        tar = tarfile.open(packagePath, mode='w:gz')
        tar.add(repositoryPath, arcname='')
        tar.close()
        log.info('OK')
        return packagePath


class UploadRemote(actions.Storage):
    def __init__(self, storage, path, name):
        super(UploadRemote, self).__init__(storage)
        self.url = path
        self.name = name
        if not self.url:
            raise ValueError('Please specify repository URL')
        if not self.name:
            rx = re.compile(r'^.*/(?P<name>.*?)(\..*)?$')
            match = rx.match(self.url)
            self.name = match.group('name')

    @chain.source
    def execute(self):
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