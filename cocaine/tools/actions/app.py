import logging
import os
import re
import shutil
import tarfile
import tempfile
import msgpack

from cocaine.asio import engine
from cocaine.asio.exceptions import LocatorResolveError
from cocaine.asio.service import Service
from cocaine.exceptions import ServiceError
from cocaine.futures import chain
from cocaine.tools import actions, log
from cocaine.tools.actions import common, readArchive, CocaineConfigReader, docker
from cocaine.tools.actions.common import NodeInfo
from cocaine.tools.error import Error as ToolsError
from cocaine.tools.installer import PythonModuleInstaller, ModuleInstallError, _locateFile
from cocaine.tools.printer import printer
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


class Specific(actions.Specific):
    def __init__(self, storage, name):
        super(Specific, self).__init__(storage, 'application', name)


class List(actions.List):
    def __init__(self, storage):
        super(List, self).__init__('manifests', APPS_TAGS, storage)


class View(actions.View):
    def __init__(self, storage, name):
        super(View, self).__init__(storage, 'application', name, 'manifests')


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
        with printer('Loading manifest'):
            manifest = CocaineConfigReader.load(self.manifest)

        with printer('Reading package "%s"', self.package):
            package = msgpack.dumps(readArchive(self.package))

        with printer('Uploading manifest'):
            yield self.storage.write('manifests', self.name, manifest, APPS_TAGS)

        with printer('Uploading application "%s"', self.name):
            yield self.storage.write('apps', self.name, package, APPS_TAGS)


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
        with printer('Removing "%s"', self.name):
            apps = yield List(self.storage).execute()
            if self.name not in apps:
                raise ToolsError('application "{0}" does not exist'.format(self.name))
            yield self.storage.remove('manifests', self.name)
            yield self.storage.remove('apps', self.name)


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
        return self.node.start_app({
            self.name: self.profile
        })


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
    def __init__(self, node, storage, locator, name):
        super(Check, self).__init__(node)
        self.name = name
        self.storage = storage
        self.locator = locator
        if not self.name:
            raise ValueError('Please specify application name')

    @chain.source
    def execute(self):
        log.info('Checking "%s"... ', self.name)
        apps = yield List(self.storage).execute()
        if self.name not in apps:
            raise ToolsError('not available')

        app = Service(self.name, blockingConnect=False)
        try:
            yield app.connectThroughLocator(self.locator)
            info = yield app.info()
            log.info(info['state'])
        except (LocatorResolveError, ServiceError):
            raise ToolsError('stopped')


class DockerUpload(actions.Storage):
    def __init__(self, storage, path, name, manifest, address, registry=''):
        super(DockerUpload, self).__init__(storage)
        self.path = path
        self.name = name or os.path.basename(os.path.abspath(path))
        if registry:
            self.name = '{}/{}'.format(registry, self.name)
        print(self.name)

        self.manifest = manifest

        self.client = docker.Client(address)

        if not os.path.exists(os.path.join(path, 'Dockerfile')):
            raise ValueError('Dockerfile not found')
        if not address:
            raise ValueError('Docker address is not specified')

    @engine.asynchronous
    def execute(self):
        response = yield self.client.build(self.path, tag=self.name, streaming=self._on_read)
        if response.code != 200:
            raise ToolsError('upload failed with error code {}'.format(response.code))

        print(self.name)
        response = yield self.client.push(self.name, {}, streaming=self._on_read)
        if response.code != 200:
            raise ToolsError('upload failed with error code {}'.format(response.code))

    def _on_read(self, value):
        print(value)


class LocalUpload(actions.Storage):
    def __init__(self, storage, path, name, manifest):
        super(LocalUpload, self).__init__(storage)
        self.path = path or os.path.curdir
        self.name = name
        self.manifest = manifest
        self.virtualEnvironmentType = 'None'
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
                manifestPath = _locateFile(self.path, 'manifest.json')
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
        with printer('Creating package'):
            packagePath = os.path.join(repositoryPath, 'package.tar.gz')
            tar = tarfile.open(packagePath, mode='w:gz')
            tar.add(repositoryPath, arcname='')
            tar.close()
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