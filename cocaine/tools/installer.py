import json
import os
import subprocess
import tempfile
from threading import Lock
import logging

from cocaine.tools.repository import GitRepositoryDownloader, RepositoryDownloadError

__author__ = 'EvgenySafronov <division494@gmail.com>'


class ModuleInstallError(Exception):
    pass


log = logging.getLogger(__name__)


class ModuleInstaller(object):
    def install(self):
        raise NotImplementedError


class PythonModuleInstaller(ModuleInstaller):
    virtualEnvGlobalLock = Lock()

    def __init__(self, path, manifestPath):
        self.path = path
        self.manifestPath = manifestPath
        self.devnull = open(os.devnull, 'w')

    def install(self):
        log.debug('Start installing python module')
        venv = self.createVirtualEnvironment()
        self.createBootstrap()
        self.installCocaineFramework(venv)
        self.installRequirements(venv)
        log.debug('Python module has been successfully installed')

    def createVirtualEnvironment(self):
        try:
            with self.virtualEnvGlobalLock:
                log.debug('Creating virtual environment ...')
                import virtualenv
                venv = os.path.join(self.path, 'venv')
                virtualenv.create_environment(venv)
                log.debug('Virtual environment has been successfully created in "{0}"'.format(venv))
                return venv
        except ImportError:
            raise ModuleInstallError('Module virtualenv is not installed, so a new environment cannot be created')

    def createBootstrap(self):
        log.debug('Creating bootstrap script ...')
        initialManifestPath = os.path.join(self.path, 'manifest.json')
        if os.path.exists(initialManifestPath):
            with open(initialManifestPath) as manifestFh:
                try:
                    manifest = json.loads(manifestFh.read())
                    slave = manifest['slave']

                    bootstrapPath = os.path.join(self.path, 'bootstrap.sh')
                    with open(bootstrapPath, 'w') as fh:
                        fh.write('#!/bin/sh\n')
                        fh.write('source venv/bin/activate\n')
                        fh.write('python {0} $@\n'.format(slave))
                    os.chmod(bootstrapPath, 0755)

                    with open(self.manifestPath, 'w') as fh:
                        manifest['slave'] = 'bootstrap.sh'
                        fh.write(json.dumps(manifest))
                except ValueError as err:
                    raise ModuleInstallError(err.message)
                except KeyError:
                    raise ModuleInstallError('Slave is not specified')
        else:
            raise ModuleInstallError('Manifest file (manifest.json) does not exist')

    def installCocaineFramework(self, venv):
        log.debug('Downloading cocaine-framework-python ...')
        cocaineFrameworkUrl = 'git@github.com:cocaine/cocaine-framework-python.git'
        cocaineFrameworkPath = tempfile.mkdtemp()
        downloader = GitRepositoryDownloader()
        try:
            downloader.download(cocaineFrameworkUrl, cocaineFrameworkPath)
        except RepositoryDownloadError as err:
            raise ModuleInstallError(err.message)

        log.debug('Installing cocaine-framework-python ...')
        python = os.path.join(venv, 'bin', 'python')
        process = subprocess.Popen([python, 'setup.py', 'install'],
                                   cwd=cocaineFrameworkPath,
                                   stdout=self.devnull,
                                   stderr=self.devnull)
        process.wait()
        if process.returncode != 0:
            raise ModuleInstallError()
        else:
            log.debug('Cocaine-framework-python has been successfully installed')

    def installRequirements(self, venv):
        log.debug('Installing requirements ...')
        requirementsPath = os.path.join(self.path, 'requirements.txt')
        if os.path.exists(requirementsPath):
            with open(requirementsPath) as fh:
                requirements = [requirement.strip() for requirement in fh.readlines()]
                log.debug('Requirements found: [{0}]'.format(', '.join(requirements)))
                _pip = os.path.join(venv, 'bin', 'pip')
                for requirement in requirements:
                    log.debug('Installing "{0}" ...'.format(requirement))
                    process = subprocess.Popen([_pip, 'install', requirement],
                                               stdout=self.devnull,
                                               stderr=self.devnull)
                    process.wait()
                    if process.returncode != 0:
                        raise ModuleInstallError()
                    else:
                        log.debug('Successfully installed "{0}"'.format(requirement))
                log.debug('All requirements has been successfully installed')
        else:
            log.debug('Requirements file (requirements.txt) does not exist')