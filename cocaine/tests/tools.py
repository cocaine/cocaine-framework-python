# coding=utf-8
import StringIO
import json
import os
import re
import shutil
from string import Template
import subprocess
import tarfile
import time
import unittest
from mock import Mock

import msgpack
import sys
from cocaine.tools.tools import AppListAction, APPS_TAGS, AppViewAction
from cocaine.tools.tools_sync import Storage, upload_app


__author__ = 'EvgenySafronov <division494@gmail.com>'


# class Deprecated_CocaineToolsTestCase(object):
#     work_dirs = ['plugins', 'runtime', 'spool', 'storage', 'storage/cache', 'storage/core']
#     config_dir = os.path.join(os.path.dirname(__file__), 'cocaine/tests/config')
#     example_dir = os.path.join(os.path.dirname(__file__), 'cocaine/tests/example')
#
#     @classmethod
#     def setUpSpecialDirs(cls):
#         for word_dir in cls.work_dirs:
#             directory = os.path.join(cls.config_dir, word_dir)
#             shutil.rmtree(directory, ignore_errors=True)
#             os.mkdir(directory)
#
#     @classmethod
#     def setUpClass(cls):
#         cls.setUpSpecialDirs()
#
#         # Create cocaine runtime config file from local context
#         config_filename = os.path.join(cls.config_dir, 'config.json')
#         with open(config_filename, 'r') as fh, open('/tmp/config.json', 'w') as temp:
#             template = Template(fh.read())
#             content = template.substitute({
#                 'plugins': os.path.join(cls.config_dir, 'plugins'),
#                 'runtime': os.path.join(cls.config_dir, 'runtime'),
#                 'spool': os.path.join(cls.config_dir, 'spool'),
#                 'storage_core': os.path.join(cls.config_dir, 'storage', 'core'),
#                 'storage_cache': os.path.join(cls.config_dir, 'storage', 'cache')
#             })
#             temp.write(content)
#
#         print('Starting cocaine runtime process ...')
#         subprocess.Popen(
#             [COCAINE_RUNTIME_PATH, '--daemonize', '--configuration', temp.name]
#         )
#         time.sleep(0.5)
#
#     @classmethod
#     def tearDownClass(cls):
#         #todo: Cocaine runtime places its pid in ./runtime/cocained.pid so killall is not necessary
#         print('Terminating cocaine runtime process ...')
#         os.system('killall -9 cocaine-runtime')
#         for word_dir in cls.work_dirs:
#             directory = os.path.join(cls.config_dir, word_dir)
#             shutil.rmtree(directory, ignore_errors=True)
#
#     def createManifestFileFromTemplate(self, manifest_filename, slave_filename):
#         with open(manifest_filename, 'r') as expected_fh, open('/tmp/manifest.json', 'w') as temp:
#             template = Template(expected_fh.read())
#             content = template.substitute({
#                 'slave': slave_filename
#             })
#             temp.write(content)
#
#     def createPackageFile(self, slave_filename):
#         with tarfile.open('/tmp/package.tar.gz', 'w:gz') as tar:
#             tar.add(slave_filename, arcname='test_example.py')
#
#     def test_UploadApp(self):
#         manifest_filename = os.path.join(self.example_dir, 'manifest.json')
#         slave_filename = os.path.abspath(os.path.join(self.example_dir, 'test_example.py'))
#         self.createManifestFileFromTemplate(manifest_filename, slave_filename)
#         self.createPackageFile(slave_filename)
#
#         class Options:
#             name = 'test_example'
#             manifest = '/tmp/manifest.json'
#             package = '/tmp/package.tar.gz'
#
#         storage = Storage(hostname='localhost', port=10053, timeout=2)
#         options = Options()
#         upload_app(storage, options)
#         time.sleep(0.5)
#
#         # Check file exists
#         actual_app_filename = os.path.join(self.config_dir, 'storage', 'core', 'apps', 'test_example')
#         actual_manifest_filename = os.path.join(self.config_dir, 'storage', 'core', 'manifests', 'test_example')
#         self.assertTrue(os.path.exists(actual_app_filename))
#         self.assertTrue(os.path.exists(actual_manifest_filename))
#
#         # Compare manifests
#         with open('/tmp/manifest.json', 'r') as expected_fh, open(actual_manifest_filename, 'r') as actual_fh:
#             expected = msgpack.packb(json.loads(expected_fh.read()))
#             self.assertEqual(expected, actual_fh.read())
#
#         # Compare apps
#         with open('/tmp/package.tar.gz', 'r') as expected_fh, open(actual_app_filename, 'r') as actual_fh:
#             expected = msgpack.packb(expected_fh.read())
#             self.assertEqual(expected, actual_fh.read())
#
#         # Check symlinks
#         self.assertEqual(
#             os.path.realpath(os.path.join(self.config_dir, 'storage', 'core', 'manifests', 'apps', 'test_example')),
#             actual_manifest_filename
#         )
#         self.assertEqual(
#             os.path.realpath(os.path.join(self.config_dir, 'storage', 'core', 'apps', 'apps', 'test_example')),
#             actual_app_filename
#         )
#
#     def test_RaisesExceptionWhenThereIsWrongManifestFileName(self):
#         class Options:
#             name = 'test_example'
#             manifest = 'wrongManifest.json'
#             package = '/tmp/package.tar.gz'
#
#         storage = Storage(hostname='localhost', port=10053, timeout=2)
#         options = Options()
#         self.assertRaises(ValueError, upload_app, storage, options)
#
#     def test_RaisesExceptionWhenThereIsWrongManifestFileFormat(self):
#         class Options:
#             name = 'test_example'
#             manifest = '/tmp/package.tar.gz'
#             package = '/tmp/package.tar.gz'
#
#         storage = Storage(hostname='localhost', port=10053, timeout=2)
#         options = Options()
#         self.assertRaises(ValueError, upload_app, storage, options)
#
#     def test_RaisesValueErrorWhenPackageFileIsAbsent(self):
#         class Options:
#             name = 'test_example'
#             manifest = '/tmp/manifest.json'
#             package = 'wrongPackage'
#
#         storage = Storage(hostname='localhost', port=10053, timeout=2)
#         options = Options()
#         self.assertRaises(ValueError, upload_app, storage, options)
#
#     def test_RaisesValueErrorWhenPackageFileIsNotTar(self):
#         class Options:
#             name = 'test_example'
#             manifest = '/tmp/manifest.json'
#             package = '/tmp/manifest.json'
#
#         storage = Storage(hostname='localhost', port=10053, timeout=2)
#         options = Options()
#         self.assertRaises(ValueError, upload_app, storage, options)
#
#     def test_z1ShowAppList(self):
#         storage = Storage(hostname='localhost', port=10053, timeout=2)
#         self.assertListEqual(['1. test_example'], storage.apps())
#
#
# class CocaineToolsTestCase(unittest.TestCase):
#     def test_AppList(self):
#         storage = Mock()
#         action = AppListAction(storage)
#         action.execute()
#         storage.find.assert_called_once_with('manifests', APPS_TAGS)
#
#     def test_AppView(self):
#         storage = Mock()
#         action = AppViewAction(storage, **{'name': 'name'})
#         action.execute()
#         storage.read.assert_called_once_with('manifests', 'name')
#
#     def test_AppViewThrowsExceptionOnNoneAppNameSpecified(self):
#         storage = Mock()
#         self.assertRaises(ValueError, AppViewAction, storage, **{'name': ''})
#
#


COCAINE_RUNTIME_PATH = '/home/evgeny/sandbox/cocaine-core/build/cocaine-runtime'
ADEQUATE_TIMEOUT = 0.5
PYTHON = '/usr/bin/python'
COCAINE_TOOLS = '/home/evgeny/sandbox/cocaine-framework-python/scripts/cocaine-tool'


class Context(object):
    CONFIG = {
        "version": 2,
        "paths": {
            "plugins": os.path.join(os.path.dirname(__file__), 'root', 'plugins'),
            "runtime": os.path.join(os.path.dirname(__file__), 'root', 'runtime'),
            "spool": os.path.join(os.path.dirname(__file__), 'root', 'spool')
        },
        "services": {
            "logging": {
                "type": "logging"
            },
            "storage": {
                "type": "storage"
            },
            "node": {
                "type": "node",
                "args": {
                    "announce": ["tcp://*:5001"],
                    "announce-interval": 1,
                    "runlist": "default"
                }
            }
        },
        "storages": {
            "core": {
                "type": "files",
                "args": {
                    "path": os.path.join(os.path.dirname(__file__), 'root', 'storage', 'core')
                }
            },
            "cache": {
                "type": "files",
                "args": {
                    "path": os.path.join(os.path.dirname(__file__), 'root', 'storage', 'cache')
                }
            }
        },
        "loggers": {
            "core": {
                "type": "stdout",
                "args": {
                    "verbosity": "info"
                }
            },
            "tools": {
                "type": "stdout",
                "args": {
                    "verbosity": "error"
                }

            }
        }
    }

    MANIFEST = {
        'slave': os.path.join(os.path.dirname(__file__), 'config', 'test_example.py'),
        'drivers': {
            'fs': {
                'type': 'fs',
                'args': {
                    'emit': 'fs',
                    'path': '/tmp/1'
                }
            }
        }
    }

    PROFILE = {
        'pool-limit': 4
    }

    RUNLIST = {
        'test': 'profile'
    }

    SLAVE = '''
        from cocaine.decorators import fs
        from cocaine.worker import Worker


        @fs
        def epicFail(request, response):
            stat = yield request.read()
            response.write("OK")
            response.close()

        W = Worker()
        W.run({'fs': epicFail})
    '''


class FunctionalTests(unittest.TestCase):
    relativeWorkingPaths = ['plugins', 'runtime', 'spool', 'storage', 'storage/cache', 'storage/core']
    rootPath = os.path.join(os.path.dirname(__file__), 'root')
    workPaths = [os.path.join(rootPath, relativeWorkingPath) for relativeWorkingPath in relativeWorkingPaths]
    configDirPath = os.path.join(os.path.dirname(__file__), 'config')

    manifestFilename = os.path.join(configDirPath, 'manifest.json')
    packageFilename = os.path.join(configDirPath, 'package.tar.gz')
    profileFilename = os.path.join(configDirPath, 'profile.json')
    runlistFilename = os.path.join(configDirPath, 'runlist.json')
    workPaths.append(configDirPath)

    @classmethod
    def setUpSpecialDirs(cls):
        for path in cls.workPaths:
            shutil.rmtree(path, ignore_errors=True)
            os.makedirs(path)

    @classmethod
    def setUpClass(cls):
        cls.setUpSpecialDirs()

        # Create cocaine runtime config file from local context
        configFilename = os.path.join(cls.configDirPath, 'config.json')
        with open(configFilename, 'w') as fh:
            fh.write(json.dumps(Context.CONFIG, indent=4))

        # Create application manifest
        with open(cls.manifestFilename, 'w+') as fh:
            fh.write(json.dumps(Context.MANIFEST, indent=4))

        # Create application package
        with tarfile.open(cls.packageFilename, 'w:gz') as tar:
            tarinfo = tarfile.TarInfo('app.py')
            tarinfo.size = len(Context.SLAVE)
            tar.addfile(tarinfo, StringIO.StringIO(Context.SLAVE))

        # Create profile
        with open(cls.profileFilename, 'w') as fh:
            fh.write(json.dumps(Context.PROFILE, indent=4))


        # Create runlist
        with open(cls.runlistFilename, 'w') as fh:
            fh.write(json.dumps(Context.RUNLIST, indent=4))

        # Start cocaine-runtime
        sys.stderr.write('Starting cocaine runtime process ...')
        subprocess.Popen([COCAINE_RUNTIME_PATH, '--daemonize', '--configuration', configFilename])
        sys.stderr.write(' OK\n')
        time.sleep(ADEQUATE_TIMEOUT)

    @classmethod
    def tearDownClass(cls):
        sys.stderr.write('Terminating cocaine runtime process ...')
        try:
            with open(os.path.join(cls.rootPath, 'runtime', 'cocained.pid'), 'r') as fh:
                pid = fh.read()
                os.system('kill -9 {pid}'.format(pid=pid))
                sys.stderr.write(' OK\n')
        except IOError as err:
            sys.stderr.write(' FAIL - {0}\n'.format(err))

        for path in cls.workPaths:
            shutil.rmtree(path, ignore_errors=True)

    def assertEqualContent(self, expected, actual):
        self.assertEqual(re.sub(r'\s', '', expected),
                         re.sub(r'\s', '', actual))


    def runBadlyAndCheckResult(self, command, expected, errorCode):
        cmd = [PYTHON, COCAINE_TOOLS]
        cmd.extend(command)
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = process.communicate()
        self.assertEqual(errorCode, process.returncode)
        self.assertEqual(expected, err)

    def test_AppUploadEmptyName(self):
        expected = 'Please specify name of the app\n'
        self.runBadlyAndCheckResult(['app', 'upload', '--name='], expected, 1)

    def test_AppUploadEmptyManifest(self):
        expected = 'Please specify manifest of the app\n'
        self.runBadlyAndCheckResult(['app', 'upload', '--name=test', '--manifest='], expected, 1)

    def test_AppUploadEmptyPackage(self):
        expected = 'Please specify package of the app\n'
        self.runBadlyAndCheckResult(['app', 'upload', '--name=test', '--manifest={0}'.format(self.manifestFilename),
                                     '--package='], expected, 1)

    def test_AppUpload(self):
        expected = 'The app "test" has been successfully uploaded\n'
        actual = subprocess.check_output([PYTHON, COCAINE_TOOLS, 'app', 'upload',
                                          '--name=test',
                                          '--manifest={0}'.format(self.manifestFilename),
                                          '--package={0}'.format(self.packageFilename)])
        self.assertEqual(expected, actual)

    def test_z0AppList(self):
        expected = 'Currently uploaded apps:\n\t1. test\n'
        actual = subprocess.check_output([PYTHON, COCAINE_TOOLS, 'app', 'list'])
        self.assertEqual(expected, actual)

    def test_AppViewWrongName(self):
        expected = 'Specify name of application\n'
        self.runBadlyAndCheckResult(['app', 'view', '--name='], expected, 1)

    def test_AppView(self):
        actual = subprocess.check_output([PYTHON, COCAINE_TOOLS, 'app', 'view',
                                          '--name=test'])
        self.assertEqualContent(json.dumps(Context.MANIFEST), actual)

    def test_AppRemoveEmptyName(self):
        expected = 'Empty application name\n'
        self.runBadlyAndCheckResult(['app', 'remove', '--name='], expected, 1)

    def test_z9AppRemove(self):
        expected = 'The app "test" has been successfully removed\n'
        actual = subprocess.check_output([PYTHON, COCAINE_TOOLS, 'app', 'remove',
                                          '--name=test'])
        self.assertEqual(expected, actual)

    # ################# PROFILES #################
    def test_ProfileUploadEmptyName(self):
        expected = 'Please specify profile name\n'
        self.runBadlyAndCheckResult(['profile', 'upload', '--name='], expected, 1)

    def test_ProfileUploadEmptyProfile(self):
        expected = 'Please specify profile file path\n'
        self.runBadlyAndCheckResult(['profile', 'upload', '--name=profile', '--profile='], expected, 1)

    def test_ProfileUpload(self):
        expected = 'The profile "profile" has been successfully uploaded\n'
        actual = subprocess.check_output([PYTHON, COCAINE_TOOLS, 'profile', 'upload',
                                          '--name=profile',
                                          '--profile={0}'.format(self.profileFilename)])
        self.assertEqual(expected, actual)

    def test_z0ProfileList(self):
        expected = 'Currently uploaded profiles:\n\t1. profile\n'
        actual = subprocess.check_output([PYTHON, COCAINE_TOOLS, 'profile', 'list'])
        self.assertEqual(expected, actual)

    def test_ProfileViewEmptyName(self):
        expected = 'Please specify profile name\n'
        self.runBadlyAndCheckResult(['profile', 'view', '--name='], expected, 1)

    def test_ProfileView(self):
        actual = subprocess.check_output([PYTHON, COCAINE_TOOLS, 'profile', 'view',
                                          '--name=profile'])
        self.assertEqualContent(json.dumps(Context.PROFILE), actual)

    def test_ProfileRemoveEmptyName(self):
        expected = 'Please specify profile name\n'
        self.runBadlyAndCheckResult(['profile', 'remove', '--name='], expected, 1)

    def test_z9ProfileRemove(self):
        expected = 'The profile "profile" has been successfully removed\n'
        actual = subprocess.check_output([PYTHON, COCAINE_TOOLS, 'profile', 'remove',
                                          '--name=profile'])
        self.assertEqual(expected, actual)

    # ################# RUNLISTS #################
    def test_RunlistUploadEmptyName(self):
        expected = 'Please specify runlist name\n'
        self.runBadlyAndCheckResult(['runlist', 'upload', '--name='], expected, 1)

    def test_RunlistUploadEmptyProfile(self):
        expected = 'Please specify runlist profile file path\n'
        self.runBadlyAndCheckResult(['runlist', 'upload', '--name=runlist', '--runlist='], expected, 1)

    def test_RunlistUpload(self):
        expected = 'The runlist "runlist" has been successfully uploaded\n'
        actual = subprocess.check_output([PYTHON, COCAINE_TOOLS, 'runlist', 'upload',
                                          '--name=runlist',
                                          '--runlist={0}'.format(self.runlistFilename)])
        self.assertEqual(expected, actual)

    def test_z0RunlistList(self):
        expected = '''Currently uploaded runlists:
            \t1. runlist
        '''
        actual = subprocess.check_output([PYTHON, COCAINE_TOOLS, 'runlist', 'list'])
        self.assertEqualContent(expected, actual)

    def test_RunlistViewEmptyName(self):
        expected = 'Please specify runlist name\n'
        self.runBadlyAndCheckResult(['runlist', 'view', '--name='], expected, 1)

    def test_RunlistView(self):
        actual = subprocess.check_output([PYTHON, COCAINE_TOOLS, 'runlist', 'view',
                                          '--name=runlist'])
        self.assertEqualContent(json.dumps(Context.RUNLIST), actual)

    def test_RunlistRemoveEmptyName(self):
        expected = 'Please specify runlist name\n'
        self.runBadlyAndCheckResult(['runlist', 'remove', '--name='], expected, 1)

    def test_z9RunlistRemove(self):
        expected = 'The runlist "runlist" has been successfully removed\n'
        actual = subprocess.check_output([PYTHON, COCAINE_TOOLS, 'runlist', 'remove',
                                          '--name=runlist'])
        self.assertEqual(expected, actual)

    def test_CrashlogListEmptyName(self):
        expected = 'Please specify crashlog name\n'
        self.runBadlyAndCheckResult(['crashlog', 'list'], expected, 1)

if __name__ == '__main__':
    unittest.main()