# coding=utf-8
import StringIO
from inspect import getmembers
import inspect
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
        'slave': os.path.join(os.path.dirname(__file__), 'config', 'app.py'),
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

    applicationFilename = os.path.join(configDirPath, 'app.py')
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

        # Create application
        with open(cls.applicationFilename, 'w') as fh:
            fh.write(json.dumps(Context.SLAVE))

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
            pass#shutil.rmtree(path, ignore_errors=True)

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


class SomeTests(FunctionalTests):
    def test_0AppUpload(self):
        expected = 'The app "test" has been successfully uploaded\n'
        actual = subprocess.check_output([PYTHON, COCAINE_TOOLS, 'app', 'upload',
                                          '--name=test',
                                          '--manifest={0}'.format(self.manifestFilename),
                                          '--package={0}'.format(self.packageFilename)])
        self.assertEqual(expected, actual)

    def test_1AppList(self):
        expected = 'Currently uploaded apps:\n\t1. test\n'
        actual = subprocess.check_output([PYTHON, COCAINE_TOOLS, 'app', 'list'])
        self.assertEqual(expected, actual)

    def test_1AppView(self):
        actual = subprocess.check_output([PYTHON, COCAINE_TOOLS, 'app', 'view',
                                          '--name=test'])
        self.assertEqualContent(json.dumps(Context.MANIFEST), actual)

    def test_9AppRemove(self):
        expected = 'The app "test" has been successfully removed\n'
        actual = subprocess.check_output([PYTHON, COCAINE_TOOLS, 'app', 'remove',
                                          '--name=test'])
        self.assertEqual(expected, actual)

    def test_1AppStart(self):
        expected = {
            'test': 'the app has been started'
        }
        actual = subprocess.check_output([PYTHON, COCAINE_TOOLS, 'app', 'start',
                                          '--name=test',
                                          '--profile=default'])
        self.assertEqualContent(json.dumps(expected), actual)

    def test_2AppStartAlreadyRunning(self):
        expected = {
            'test': 'the app is already running'
        }
        actual = subprocess.check_output([PYTHON, COCAINE_TOOLS, 'app', 'start',
                                          '--name=test',
                                          '--profile=profile'])
        self.assertEqualContent(json.dumps(expected), actual)

    def test_2AppStartNotDeployed(self):
        expected = {
            'fail': ('unable to fetch the \'manifests/fail\' object from the storage - '
                     'the specified object has not been found')
        }
        actual = subprocess.check_output([PYTHON, COCAINE_TOOLS, 'app', 'start',
                                          '--name=fail',
                                          '--profile=profile'])
        self.assertEqualContent(json.dumps(expected), actual)

    #todo: Test start app with wrong profile
    #todo: Test stopping running app
    #todo: Test stopping already stopped app
    #todo: Test stopping not deployed app
    #todo: Make full test fixture for 'app check'
    #todo: Make app runlist upload feature

    def test_z1AppPause(self):
        expected = {
            'test': 'the app has been stopped'
        }
        actual = subprocess.check_output([PYTHON, COCAINE_TOOLS, 'app', 'pause',
                                          '--name=test'])
        self.assertEqualContent(json.dumps(expected), actual)

    # ################# PROFILES #################
    def test_0ProfileUpload(self):
        print(self.profileFilename)
        expected = 'The profile "default" has been successfully uploaded\n'
        actual = subprocess.check_output([PYTHON, COCAINE_TOOLS, 'profile', 'upload',
                                          '--name=default',
                                          '--profile={0}'.format(self.profileFilename)])
        self.assertEqual(expected, actual)

    def test_1ProfileList(self):
        expected = 'Currently uploaded profiles:\n\t1. default\n'
        actual = subprocess.check_output([PYTHON, COCAINE_TOOLS, 'profile', 'list'])
        self.assertEqual(expected, actual)

    def test_1ProfileView(self):
        actual = subprocess.check_output([PYTHON, COCAINE_TOOLS, 'profile', 'view',
                                          '--name=default'])
        self.assertEqualContent(json.dumps(Context.PROFILE), actual)

    def test_9ProfileRemove(self):
        expected = 'The profile "default" has been successfully removed\n'
        actual = subprocess.check_output([PYTHON, COCAINE_TOOLS, 'profile', 'remove',
                                          '--name=default'])
        self.assertEqual(expected, actual)

    # ################# RUNLISTS #################
    def test_0RunlistUpload(self):
        expected = 'The runlist "default_r" has been successfully uploaded\n'
        actual = subprocess.check_output([PYTHON, COCAINE_TOOLS, 'runlist', 'upload',
                                          '--name=default_r',
                                          '--runlist={0}'.format(self.runlistFilename)])
        self.assertEqual(expected, actual)

    def test_1RunlistList(self):
        expected = '''Currently uploaded runlists: 1. default_r'''
        actual = subprocess.check_output([PYTHON, COCAINE_TOOLS, 'runlist', 'list'])
        self.assertEqualContent(expected, actual)

    def test_1RunlistView(self):
        actual = subprocess.check_output([PYTHON, COCAINE_TOOLS, 'runlist', 'view',
                                          '--name=default_r'])
        self.assertEqualContent(json.dumps(Context.RUNLIST), actual)

    def test_9RunlistRemove(self):
        expected = 'The runlist "default_r" has been successfully removed\n'
        actual = subprocess.check_output([PYTHON, COCAINE_TOOLS, 'runlist', 'remove',
                                          '--name=default_r'])
        self.assertEqual(expected, actual)


class InvalidArgumentsTestCase(FunctionalTests):
    # ################# APPS #################
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

    def test_AppViewWrongName(self):
        expected = 'Specify name of application\n'
        self.runBadlyAndCheckResult(['app', 'view', '--name='], expected, 1)

    def test_AppRemoveEmptyName(self):
        expected = 'Empty application name\n'
        self.runBadlyAndCheckResult(['app', 'remove', '--name='], expected, 1)

    def test_AppStartEmptyName(self):
        expected = 'Please specify application name\n'
        self.runBadlyAndCheckResult(['app', 'start', '--name='], expected, 1)

    def test_z0AppStartEmptyProfile(self):
        expected = 'Please specify profile name\n'
        self.runBadlyAndCheckResult(['app', 'start', '--name=default', '--profile='], expected, 1)

    def test_AppPauseEmptyName(self):
        expected = 'Please specify application name\n'
        self.runBadlyAndCheckResult(['app', 'pause', '--name='], expected, 1)

    # ################# PROFILES #################
    def test_ProfileUploadEmptyName(self):
        expected = 'Please specify profile name\n'
        self.runBadlyAndCheckResult(['profile', 'upload', '--name='], expected, 1)

    def test_ProfileUploadEmptyProfile(self):
        expected = 'Please specify profile file path\n'
        self.runBadlyAndCheckResult(['profile', 'upload', '--name=profile', '--profile='], expected, 1)

    def test_ProfileViewEmptyName(self):
        expected = 'Please specify profile name\n'
        self.runBadlyAndCheckResult(['profile', 'view', '--name='], expected, 1)

    def test_ProfileRemoveEmptyName(self):
        expected = 'Please specify profile name\n'
        self.runBadlyAndCheckResult(['profile', 'remove', '--name='], expected, 1)

    # ################# RUNLISTS #################
    def test_RunlistUploadEmptyName(self):
        expected = 'Please specify runlist name\n'
        self.runBadlyAndCheckResult(['runlist', 'upload', '--name='], expected, 1)

    def test_RunlistUploadEmptyProfile(self):
        expected = 'Please specify runlist profile file path\n'
        self.runBadlyAndCheckResult(['runlist', 'upload', '--name=default_r', '--runlist='], expected, 1)

    def test_RunlistViewEmptyName(self):
        expected = 'Please specify runlist name\n'
        self.runBadlyAndCheckResult(['runlist', 'view', '--name='], expected, 1)

    def test_RunlistRemoveEmptyName(self):
        expected = 'Please specify runlist name\n'
        self.runBadlyAndCheckResult(['runlist', 'remove', '--name='], expected, 1)

    # ################# CRASHLOGS #################
    def test_CrashlogListEmptyName(self):
        expected = 'Please specify crashlog name\n'
        self.runBadlyAndCheckResult(['crashlog', 'list'], expected, 1)

if __name__ == '__main__':
    unittest.main()