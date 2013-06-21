import sys
import json
import subprocess
import tarfile
import tempfile
from cocaine.services import Service
from cocaine.tools.tools import ToolsError, AppUploadAction
from pip import InstallationError
from pip.vcs.git import Git, os


__author__ = 'EvgenySafronov <division494@gmail.com>'


class UploadError(ToolsError):
    pass


class RequirementInstallError(UploadError):
    pass


# Only git repository at this moment
# Only python apps at this moment
if __name__ == '__main__':
    url = 'git+file:///Users/esafronov/mock_repo/repo_echo'

    try:
        # Clone
        dest = tempfile.mkdtemp()
        trueManifestFileName = os.path.join(dest, 'manifest-start.json')
        try:
            git = Git(url=url)
            git.unpack(dest)
            print('Url "{0}" successfully cloned into "{1}"'.format(url, dest))
        except InstallationError as err:
            raise UploadError(err.message)

        # Create venv
        try:
            import virtualenv
            venv = os.path.join(dest, 'venv')
            print('Creating new virtualenv environment in {0}'.format(venv))
            virtualenv.create_environment(venv)
        except ImportError:
            raise UploadError('Module virtualenv is not installed, so a new environment cannot be created')

        # Create or modify manifest
        manifestFileName = os.path.join(dest, 'manifest.json')
        if os.path.exists(manifestFileName):
            with open(manifestFileName) as fh:
                try:
                    manifest = json.loads(fh.read())
                    print(manifest)
                    slave = manifest['slave']
                    print(slave)

                    bootstrapFileName = os.path.join(dest, 'bootstrap.sh')
                    with open(bootstrapFileName, 'w') as bfh:
                        bfh.write('#!/bin/sh\n')
                        bfh.write('source venv/bin/activate\n')
                        bfh.write('python {0} $@\n'.format(slave))
                    os.chmod(bootstrapFileName, 0755)

                    with open(trueManifestFileName, 'w') as mfh:
                        manifest['slave'] = 'bootstrap.sh'
                        mfh.write(json.dumps(manifest))
                except ValueError as err:
                    raise UploadError(err.message)
                except KeyError as err:
                    raise UploadError('Slave key is not specified')
        else:
            raise UploadError('Manifest file (manifest.json) does not exist')

        # Installing cocaine-framework-python
        cocaineFrameworkUrl = 'git+git@github.com:cocaine/cocaine-framework-python.git'
        cocaineFrameworkPath = tempfile.mkdtemp()
        print('Downloading cocaine-framework-python from "{0}" into "{1}"'.format(cocaineFrameworkUrl,
                                                                                  cocaineFrameworkPath))
        cocaineFramework = Git(url=cocaineFrameworkUrl)
        cocaineFramework.unpack(cocaineFrameworkPath)
        print('Cocaine-framework-python downloaded')

        # Installing framework python
        python = os.path.join(venv, 'bin', 'python')
        process = subprocess.Popen([python, 'setup.py', 'install'], cwd=cocaineFrameworkPath)
        process.wait()
        if process.returncode != 0:
            raise RequirementInstallError()

        # Installing requirements (if exists)
        requirementsFileName = os.path.join(dest, 'requirements.txt')
        if os.path.exists(requirementsFileName):
            # Read requirements
            with open(requirementsFileName) as fh:
                requirements = [l.strip() for l in fh.readlines()]
                # Install requirements
                _pip = os.path.join(venv, 'bin', 'pip')
                for requirement in requirements:
                    process = subprocess.Popen([_pip, 'install', requirement])
                    process.wait()
                    if process.returncode != 0:
                        raise RequirementInstallError()
        else:
            print('Requirements file (requirements.txt) does not exist')

        # Create archive
        packageFileName = os.path.join(dest, 'package.tar.gz')
        with tarfile.open(packageFileName, mode='w:gz') as tar:
            tar.add(dest, arcname='')
        print('Package file ({0}) has been created'.format(packageFileName))

        # Uploading ...
        storage = Service('storage')
        a = AppUploadAction(storage, **{
            'name': 'Sample1',
            'manifest': trueManifestFileName,
            'package': packageFileName
        })
        a.execute().get(timeout=1.0)
    except UploadError as err:
        sys.stderr.write(err.message + '\n')
        sys.exit(1)