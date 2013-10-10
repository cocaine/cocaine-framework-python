import json
import os
from string import Template
import subprocess
import tempfile
from threading import Lock
import logging

from cocaine.tools.printer import printer
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

COCAINE_INSTALL_START = 'Installing cocaine-framework-python ...'
COCAINE_INSTALL_FINISH = 'Cocaine-framework-python has been successfully installed'
COCAINE_INSTALL_ERROR = 'cocaine-framework-python install error'

BOOTSTRAP_FILENAME = 'bootstrap.sh'
BOOTSTRAP_TEMPLATE = '''#!/bin/sh
source ${virtualEnvironmentPath}/bin/activate
python ${slave} $$@
'''
BOOTSTRAP_CREATE_START = 'Creating bootstrap script ...'
BOOTSTRAP_CREATE_ERROR = 'bootstrap create error - {0}'

MANIFEST_FILENAME = 'manifest.json'
MANIFEST_READ_OK = 'Reading manifest file: "{0}"'
MANIFEST_SLAVE_PARSE_ERROR = 'manifest read error - slave is not specified'
MANIFEST_READ_ERROR = 'manifest read error - {0}'
MANIFEST_LOCATE_ERROR = 'locate manifest error - {0}'

REQUIREMENTS_FILENAME = 'requirements.txt'
REQUIREMENTS_NO_FILES_FOUND = 'No requirements found. Skipping this step ...'
REQUIREMENTS_INSTALL_START = 'Installing requirements ...'
REQUIREMENTS_INSTALL_FINISH = 'All requirements has been successfully installed'


class ModuleInstaller(object):
    def install(self):
        raise NotImplementedError


class PythonModuleInstaller(ModuleInstaller):
    virtualEnvGlobalLock = Lock()

    def __init__(self, path, outputPath, manifestPath=None, virtualEnvironmentName='venv', stream=None):
        self.path = path
        self.outputPath = outputPath
        self.manifestPath = manifestPath
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
        log.debug(BOOTSTRAP_CREATE_START)
        manifest = self._readManifest(self.path)
        self._createBootstrap(os.path.join(self.outputPath, BOOTSTRAP_FILENAME), manifest)
        self._copyManifest(os.path.join(self.outputPath, MANIFEST_FILENAME), manifest)

    def _readManifest(self, path):
        try:
            if not self.manifestPath:
                self.manifestPath = _locateFile(path, MANIFEST_FILENAME)

            with open(self.manifestPath) as fh:
                log.debug(MANIFEST_READ_OK.format(self.manifestPath))
                try:
                    manifest = json.loads(fh.read())
                    if 'slave' not in manifest:
                        raise ModuleInstallError(MANIFEST_SLAVE_PARSE_ERROR)
                    return manifest
                except (IOError, ValueError) as err:
                    raise ModuleInstallError(MANIFEST_READ_ERROR.format(err))
        except IOError as err:
            raise ModuleInstallError(MANIFEST_LOCATE_ERROR.format(err))

    def _createBootstrap(self, path, manifest):
        try:
            with open(path, 'w') as fh:
                fh.write(Template(BOOTSTRAP_TEMPLATE).substitute(**{
                    'virtualEnvironmentPath': self.virtualEnvironmentPath,
                    'slave': manifest['slave']
                }))
            os.chmod(path, 493)  # 0755
        except IOError as err:
            raise ModuleInstallError(BOOTSTRAP_CREATE_ERROR.format(err))

    def _copyManifest(self, path, manifest):
        try:
            with open(path, 'w') as fh:
                manifest['slave'] = BOOTSTRAP_FILENAME
                fh.write(json.dumps(manifest))
        except IOError as err:
            raise ModuleInstallError(BOOTSTRAP_CREATE_ERROR.format(err))

    def installCocaineFramework(self):
        path = tempfile.mkdtemp()
        downloader = GitRepositoryDownloader(stream=self.stream)
        try:
            log.debug(COCAINE_DOWNLOAD_START.format(COCAINE_PYTHON_FRAMEWORK_URL, path))
            downloader.download(COCAINE_PYTHON_FRAMEWORK_URL, path)
        except RepositoryDownloadError as err:
            raise ModuleInstallError(err)

        log.debug(COCAINE_INSTALL_START)
        python = os.path.join(self.virtualEnvironmentPath, 'bin', 'python')
        process = subprocess.Popen([python, 'setup.py', 'install', '--without-tools'],
                                   cwd=path,
                                   stdout=self.stream,
                                   stderr=self.stream)
        process.wait()
        if process.returncode != 0:
            raise ModuleInstallError(COCAINE_INSTALL_ERROR)
        log.debug(COCAINE_INSTALL_FINISH)

    def installRequirements(self):
        try:
            requirementsPath = _locateFile(self.path, REQUIREMENTS_FILENAME)
        except IOError:
            requirementsPath = ''

        if not requirementsPath:
            log.debug(REQUIREMENTS_NO_FILES_FOUND)
            return

        log.debug(REQUIREMENTS_INSTALL_START)
        _pip = os.path.join(self.virtualEnvironmentPath, 'bin', 'pip')
        process = subprocess.Popen([_pip, 'install', '-r', requirementsPath],
                                   stdout=self.stream,
                                   stderr=self.stream)
        process.wait()
        if process.returncode != 0:
            raise ModuleInstallError()
        log.debug(REQUIREMENTS_INSTALL_FINISH)


def _locateFile(path, filenameLocate):
        with printer('Locating %s', filenameLocate) as p:
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
            p('found "%s"', filename)
            return os.path.abspath(filename)