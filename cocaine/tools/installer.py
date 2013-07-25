import json
import os
from string import Template
import subprocess
import tempfile
from threading import Lock
import logging

from cocaine.tools.repository import GitRepositoryDownloader, RepositoryDownloadError

__author__ = 'EvgenySafronov <division494@gmail.com>'


class ModuleInstallError(Exception):
    pass


log = logging.getLogger(__name__)


MODULE_INSTALL_START = 'Start installing python module'
MODULE_INSTALL_FINISH = 'Python module has been successfully installed'

VENV_CREATE_START = 'Creating virtual environment ...'
VENV_CREATE_FINISH = 'Virtual environment has been successfully created in "{0}"'
VENV_CREATE_ERROR = 'Module virtualenv is not installed, so a new environment cannot be created'


COCAINE_PYTHON_FRAMEWORK_URL = 'git@github.com:cocaine/cocaine-framework-python.git'
COCAINE_DOWNLOAD_START = 'Downloading cocaine-framework-python from "{0}" to "{1}"...'

BOOTSTRAP_TEMPLATE = '''#!/bin/sh
source ${virtualEnvironmentPath}/bin/activate
python ${slave} $$@
'''


class ModuleInstaller(object):
    def install(self):
        raise NotImplementedError


class PythonModuleInstaller(ModuleInstaller):
    virtualEnvGlobalLock = Lock()

    def __init__(self, path, outputPath, virtualEnvironmentName='venv', stream=None):
        self.path = path
        self.outputPath = outputPath
        self.virtualEnvironmentPath = os.path.join(self.outputPath, virtualEnvironmentName)
        self.stream = stream or open(os.devnull, 'w')

        if not os.path.exists(self.path):
            raise ValueError('path "{0}" is not valid module path'.format(self.path))

        if not os.path.exists(self.outputPath):
            raise ValueError('path "{0}" is not valid path'.format(self.outputPath))

        if os.path.exists(self.virtualEnvironmentPath):
            raise ValueError('virtual environment is already exists in "{0}"'.format(self.virtualEnvironmentPath))

    def install(self):
        log.debug(MODULE_INSTALL_START)
        self.createVirtualEnvironment()
        self.prepareModule()
        self.installCocaineFramework()
        self.installRequirements()
        log.debug(MODULE_INSTALL_FINISH)

    def createVirtualEnvironment(self):
        try:
            with self.virtualEnvGlobalLock:
                import virtualenv
                log.debug(VENV_CREATE_START)
                virtualenv.create_environment(self.virtualEnvironmentPath)
                log.debug(VENV_CREATE_FINISH.format(self.outputPath))
        except ImportError:
            raise ModuleInstallError(VENV_CREATE_ERROR)

    def prepareModule(self):
        log.debug('Creating bootstrap script ...')
        manifest = self._readManifest(self.path)
        self._createBootstrap(os.path.join(self.outputPath, 'bootstrap.sh'), manifest)
        self._copyManifest(os.path.join(self.outputPath, 'manifest.json'), manifest)

    def _readManifest(self, path):
        try:
            manifestPath = _locateFile(path, 'manifest.json')
            with open(manifestPath) as fh:
                try:
                    manifest = json.loads(fh.read())
                    if 'slave' not in manifest:
                        raise ModuleInstallError('manifest read error - slave is not specified')
                    return manifest
                except (IOError, ValueError) as err:
                    raise ModuleInstallError('manifest read error - {0}'.format(err))
        except IOError as err:
            raise ModuleInstallError('locate manifest error - {0}'.format(err))

    def _createBootstrap(self, path, manifest):
        try:
            with open(path, 'w') as fh:
                fh.write(Template(BOOTSTRAP_TEMPLATE).substitute(**{
                    'virtualEnvironmentPath': self.virtualEnvironmentPath,
                    'slave': manifest['slave']
                }))
            os.chmod(path, 0755)
        except IOError as err:
            raise ModuleInstallError('bootstrap create error - {0}'.format(err))

    def _copyManifest(self, path, manifest):
        try:
            with open(path, 'w') as fh:
                manifest['slave'] = 'bootstrap.sh'
                fh.write(json.dumps(manifest))
        except IOError as err:
            raise ModuleInstallError('bootstrap create error - {0}'.format(err))

    def installCocaineFramework(self):
        path = tempfile.mkdtemp()
        downloader = GitRepositoryDownloader(stream=self.stream)
        try:
            log.debug(COCAINE_DOWNLOAD_START.format(COCAINE_PYTHON_FRAMEWORK_URL, path))
            downloader.download(COCAINE_PYTHON_FRAMEWORK_URL, path)
        except RepositoryDownloadError as err:
            raise ModuleInstallError(err.message)

        log.debug('Installing cocaine-framework-python ...')
        python = os.path.join(self.virtualEnvironmentPath, 'bin', 'python')
        process = subprocess.Popen([python, 'setup.py', 'install', '--without-tools'],
                                   cwd=path,
                                   stdout=self.stream,
                                   stderr=self.stream)
        process.wait()
        if process.returncode != 0:
            raise ModuleInstallError('cocaine-framework-python install error')
        log.debug('Cocaine-framework-python has been successfully installed')

    def installRequirements(self):
        try:
            requirementsPath = _locateFile(self.path, 'requirements.txt')
        except IOError:
            requirementsPath = ''

        log.debug('Installing requirements ...')
        _pip = os.path.join(self.virtualEnvironmentPath, 'bin', 'pip')
        process = subprocess.Popen([_pip, 'install', '-r', requirementsPath],
                                   stdout=self.stream,
                                   stderr=self.stream)
        process.wait()
        if process.returncode != 0:
            raise ModuleInstallError()
        log.debug('All requirements has been successfully installed')


def _locateFile(path, filenameLocate):
        basename, separator, extension = filenameLocate.partition('.')
        locatedFilenames = []
        for root, dirNames, filenames in os.walk(path):
            for filename in filenames:
                if filename.startswith(basename):
                    priority = 1
                    if root == path:
                        priority += 100
                    if filename == filenameLocate:
                        priority += 10
                    locatedFilenames.append((os.path.join(root, filename), priority))
        locatedFilenames = sorted(locatedFilenames, key=lambda filename: filename[1], reverse=True)
        log.debug('Filenames found: {0}'.format(locatedFilenames))
        if not locatedFilenames:
            raise IOError('No files found in "{0}" or subdirectories'.format(path))

        filename, priority = locatedFilenames[0]
        return os.path.abspath(filename)