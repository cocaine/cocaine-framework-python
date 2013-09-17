import json
import os
import shutil
import logging
import subprocess
import unittest
import sys
import time

__author__ = 'Evgeny Safronov <division494@gmail.com>'


log = logging.getLogger(__name__)
h = logging.StreamHandler(stream=sys.stdout)
log.addHandler(h)
log.setLevel(logging.DEBUG)

ROOT_PATH = '/Users/esafronov/testing'
PLUGINS_PATH = os.path.join(ROOT_PATH, 'usr/lib/cocaine')
RUNTIME_PATH = os.path.join(ROOT_PATH, 'var/run/cocaine')
SPOOL_PATH = os.path.join(ROOT_PATH, 'var/spool/cocaine')

COCAINE_RUNTIME_PATH = '/Users/esafronov/sandbox/cocaine-core-build/cocaine-runtime'
COCAINE_TOOL = '/Users/esafronov/sandbox/cocaine-framework-python/scripts/cocaine-tool'

config = {
    "version": 2,
    "paths": {
        "plugins": PLUGINS_PATH,
        "runtime": RUNTIME_PATH,
        "spool": SPOOL_PATH
    },
    "locator": {
        "port": 10053
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
                "path": os.path.join(ROOT_PATH, 'var/lib/cocaine')
            }
        }
    },
    "logging": {
        "core": {
            "formatter": {
                "type": "string",
                "format": "[%(time)s] [%(level)s] %(source)s: %(message)s"
            },
            "handler": {
                "type": "files",
                "path": "/dev/stdout",
                "verbosity": "info"
            }
        }
    }
}


def call(cmd):
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    p.wait()
    stdout, stderr = p.communicate()
    return p.returncode, stdout, stderr


def trim(string):
    return string.replace(' ', '').replace('\n', '')


class ToolsTestCase(unittest.TestCase):
    pid = -1

    def setUp(self):
        log.info('Cleaning up %s ...', ROOT_PATH)
        shutil.rmtree(ROOT_PATH, ignore_errors=True)

        log.info('Preparing ...')
        log.info(' - creating "%s"', ROOT_PATH)
        paths = [ROOT_PATH, PLUGINS_PATH, RUNTIME_PATH, SPOOL_PATH]
        map(lambda path: os.makedirs(path), paths)
        config_path = os.path.join(ROOT_PATH, 'config.json')
        log.info(' - creating config at "%s"', config_path)
        with open(config_path, 'w') as fh:
            fh.write(json.dumps(config))

        log.info(' - starting cocaine-runtime ...')
        p = subprocess.Popen([COCAINE_RUNTIME_PATH, '-c', config_path], stdout=subprocess.PIPE)
        self.pid = p.pid

    def tearDown(self):
        log.info('Cleaning up ...')
        log.info(' - killing cocaine-runtime (%d pid) ...', self.pid)
        if self.pid != -1:
            os.kill(self.pid, 9)
        log.info(' - cleaning up "%s" ...', ROOT_PATH)
        shutil.rmtree(ROOT_PATH, ignore_errors=True)

    def test_profile(self):
        code, out, err = call([COCAINE_TOOL, 'profile', 'upload',
                               '--name', 'test_profile',
                               '--profile', '"{}"'])
        self.assertEqual(0, code)
        self.assertEqual('The profile "test_profile" has been successfully uploaded\n', out)
        self.assertEqual('', err)

        code, out, err = call([COCAINE_TOOL, 'profile', 'list'])
        self.assertEqual(0, code)
        self.assertEqual('["test_profile"]', trim(out))
        self.assertEqual('', err)

        code, out, err = call([COCAINE_TOOL, 'profile', 'remove',
                               '--name', 'test_profile'])
        self.assertEqual(0, code)
        self.assertEqual('The profile "test_profile" has been successfully removed\n', out)
        self.assertEqual('', err)