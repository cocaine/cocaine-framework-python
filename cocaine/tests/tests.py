# coding=utf-8
import unittest
from tornado.testing import AsyncTestCase
from mockito import mock, when, verify, any
from cocaine.tools.tools import *

__author__ = 'EvgenySafronov <division494@gmail.com>'


class AppTestCase(AsyncTestCase):
    def test_AppListAction(self):
        """
        In this test we just need to be sure, that there will be `find` method invocation from `storage` object with
        specified arguments
        """
        storage = mock()
        action = AppListAction(storage, **{})
        action.execute()
        verify(storage).find('manifests', APPS_TAGS)

    def test_AppViewActionValueErrors(self):
        storage = mock()
        self.assertRaises(ValueError, AppViewAction, storage, **{})
        self.assertRaises(ValueError, AppViewAction, storage, **{'name': None})
        self.assertRaises(ValueError, AppViewAction, storage, **{'name': ''})

    def test_AppViewAction(self):
        storage = mock()
        action = AppViewAction(storage, **{'name': 'AppName'})
        action.execute()
        verify(storage).read('manifests', 'AppName')

    def test_AppUploadValueErrors(self):
        storage = mock()
        self.assertRaises(ValueError, AppUploadAction, storage, **{})
        self.assertRaises(ValueError, AppUploadAction, storage, **{'name': '', 'manifest': '', 'package': ''})
        self.assertRaises(ValueError, AppUploadAction, storage, **{'name': '', 'manifest': 'M', 'package': 'P'})
        self.assertRaises(ValueError, AppUploadAction, storage, **{'name': 'A', 'manifest': '', 'package': 'P'})
        self.assertRaises(ValueError, AppUploadAction, storage, **{'name': 'A', 'manifest': 'M', 'package': ''})

    def test_AppUploadAction(self):
        storage = mock()
        jsonEncoder = mock()
        packageEncoder = mock()
        action = AppUploadAction(storage, **{'name': 'AppName', 'manifest': 'm.json', 'package': 'p.tar.gz'})
        action.jsonEncoder = jsonEncoder
        action.packageEncoder = packageEncoder

        when(jsonEncoder).encode('m.json').thenReturn('-encodedJson-')
        when(packageEncoder).encode('p.tar.gz').thenReturn('-encodedTar-')
        when(storage).write('manifests', any(str), any(str), any(tuple)).thenReturn('Ok')
        when(storage).write('apps', any(str), any(str), any(tuple)).thenReturn('Ok')
        action.execute().get(timeout=0.1)

        verify(storage).write('manifests', 'AppName', '-encodedJson-', APPS_TAGS)
        verify(storage).write('apps', 'AppName', '-encodedTar-', APPS_TAGS)

    def test_AppRemoveActionValueErrors(self):
        storage = mock()
        self.assertRaises(ValueError, AppRemoveAction, storage, **{})
        self.assertRaises(ValueError, AppRemoveAction, storage, **{'name': ''})

    def test_AppRemove(self):
        storage = mock()
        action = AppRemoveAction(storage, **{'name': 'AppName'})
        when(storage).remove('manifests', any(str)).thenReturn('Ok')
        when(storage).remove('apps', any(str)).thenReturn('Ok')
        action.execute().get(timeout=0.1)

        verify(storage).remove('manifests', 'AppName')
        verify(storage).remove('apps', 'AppName')


if __name__ == '__main__':
    unittest.main()
