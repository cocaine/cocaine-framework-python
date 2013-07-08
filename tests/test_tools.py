# coding=utf-8
from __future__ import absolute_import
import unittest
from cocaine.tools.tags import APPS_TAGS, PROFILES_TAGS, RUNLISTS_TAGS
from cocaine.tools.actions import common, app, profile, runlist, crashlog
import msgpack
from mockito import mock, when, verify, any, unstub
from cocaine.testing.mocks import CallableMock
from cocaine.futures.chain import Chain
from cocaine.exceptions import ServiceError, ToolsError, ServiceCallError


__author__ = 'EvgenySafronov <division494@gmail.com>'


#todo: doc. merge. test & profit


def verifyInit(patchedClassName, expected):
    def decorator(func):
        def wrapper(self):
            def verify(*args, **kwargs):
                self.assertEqual(expected, kwargs)
            patchedClass = eval(patchedClassName)
            temp = patchedClass.__init__
            try:
                patchedClass.__init__ = verify
                func(self)
            finally:
                patchedClass.__init__ = temp
        return wrapper
    return decorator


class AppTestCase(unittest.TestCase):
    def tearDown(self):
        unstub()

    def test_AppListAction(self):
        """
        In this test we just need to be sure, that there will be `find` method invocation from `storage` object with
        specified arguments
        """
        storage = mock()
        action = app.List(storage, **{})
        action.execute()
        verify(storage).find('manifests', APPS_TAGS)

    def test_AppViewActionValueErrors(self):
        storage = mock()
        self.assertRaises(ValueError, app.View, storage, **{})
        self.assertRaises(ValueError, app.View, storage, **{'name': None})
        self.assertRaises(ValueError, app.View, storage, **{'name': ''})

    def test_AppViewAction(self):
        storage = mock()
        action = app.View(storage, **{'name': 'AppName'})
        action.execute()
        verify(storage).read('manifests', 'AppName')

    def test_AppUploadValueErrors(self):
        storage = mock()
        self.assertRaises(ValueError, app.Upload, storage, **{})
        self.assertRaises(ValueError, app.Upload, storage, **{'name': '', 'manifest': '', 'package': ''})
        self.assertRaises(ValueError, app.Upload, storage, **{'name': '', 'manifest': 'M', 'package': 'P'})
        self.assertRaises(ValueError, app.Upload, storage, **{'name': 'A', 'manifest': '', 'package': 'P'})
        self.assertRaises(ValueError, app.Upload, storage, **{'name': 'A', 'manifest': 'M', 'package': ''})

    def test_AppUploadAction(self):
        storage = mock()
        jsonEncoder = mock()
        packageEncoder = mock()
        action = app.Upload(storage, **{'name': 'AppName', 'manifest': 'm.json', 'package': 'p.tar.gz'})
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
        self.assertRaises(ValueError, app.Remove, storage, **{})
        self.assertRaises(ValueError, app.Remove, storage, **{'name': ''})

    def test_AppRemove(self):
        storage = mock()
        action = app.Remove(storage, **{'name': 'AppName'})
        when(storage).remove('manifests', any(str)).thenReturn('Ok')
        when(storage).remove('apps', any(str)).thenReturn('Ok')
        action.execute().get(timeout=0.1)

        verify(storage).remove('manifests', 'AppName')
        verify(storage).remove('apps', 'AppName')

    def test_AppStartActionValueErrors(self):
        node = mock()
        self.assertRaises(ValueError, app.Start, node, **{})
        self.assertRaises(ValueError, app.Start, node, **{'name': '', 'profile': 'P'})
        self.assertRaises(ValueError, app.Start, node, **{'name': 'N', 'profile': ''})

    def test_AppStartAction(self):
        node = mock()
        action = app.Start(node, **{'name': 'AppName', 'profile': 'ProfileName'})
        action.execute()

        verify(node).start_app({'AppName': 'ProfileName'})

    def test_AppPauseActionValueErrors(self):
        node = mock()
        self.assertRaises(ValueError, app.Stop, node, **{})
        self.assertRaises(ValueError, app.Stop, node, **{'name': ''})

    def test_AppPauseAction(self):
        node = mock()
        action = app.Stop(node, **{'name': 'AppName'})
        action.execute()

        verify(node).pause_app(['AppName'])

    def test_AppCheckActionValueErrors(self):
        node = mock()
        self.assertRaises(ValueError, app.Check, node, **{})
        self.assertRaises(ValueError, app.Check, node, **{'name': ''})

    def test_AppCheckAction(self):
        node = mock()
        action = app.Check(node, **{'name': 'AppName'})
        mockInfo = {
            'apps': {
                'AppName': {
                    'load-median': 0,
                    'profile': 'ProfileName',
                    'sessions': {
                        'pending': 0
                    },
                    'state': 'running',
                }
            }
        }
        when(node).info().thenReturn(Chain([lambda: mockInfo]))
        actual = action.execute().get(timeout=0.1)

        verify(node).info()
        self.assertEqual({'AppName': 'running'}, actual)

    def test_AppCheckActionReturnsStoppedOrMissingWhenApplicationIsNotFound(self):
        node = mock()
        action = app.Check(node, **{'name': 'AppName'})
        mockInfo = {
            'apps': {
            }
        }
        when(node).info().thenReturn(Chain([lambda: mockInfo]))
        actual = action.execute().get(timeout=0.1)

        verify(node).info()
        self.assertEqual({'AppName': 'stopped or missing'}, actual)

    def test_AppRestartActionValueErrors(self):
        node = mock()
        self.assertRaises(ValueError, app.Restart, node, **{})
        self.assertRaises(ValueError, app.Restart, node, **{'name': ''})

    @verifyInit('AppPauseAction', {'host': '', 'port': '', 'name': 'AppName'})
    @verifyInit('AppStartAction', {'host': '', 'port': '', 'name': 'AppName', 'profile': 'ProfileName'})
    def test_AppRestartActionAppIsRunningProfileIsNotSpecified(self):
        node = mock()
        action = app.Restart(node, **{'name': 'AppName', 'host': '', 'port': ''})
        when(common.NodeInfo).execute().thenReturn(Chain([lambda: {
            'apps': {
                'AppName': {
                    'profile': 'ProfileName',
                    'state': 'running',
                }
            }
        }]))

        when(app.Stop).execute().thenReturn(Chain([lambda: {'AppName': 'Stopped'}]))
        when(app.Start).execute().thenReturn(Chain([lambda: {'AppName': 'Started'}]))
        action.execute().get()

        verify(common.NodeInfo).execute()
        verify(app.Stop).execute()
        verify(app.Start).execute()

    @verifyInit('AppPauseAction', {'host': '', 'port': '', 'name': 'AppName', 'profile': 'NewProfile'})
    @verifyInit('AppStartAction', {'host': '', 'port': '', 'name': 'AppName', 'profile': 'NewProfile'})
    def test_AppRestartActionAppIsRunningProfileIsSpecified(self):
        node = mock()
        action = app.Restart(node, **{'name': 'AppName', 'profile': 'NewProfile', 'host': '', 'port': ''})
        when(common.NodeInfo).execute().thenReturn(Chain([lambda: {
            'apps': {
                'AppName': {
                    'profile': 'ProfileName',
                    'state': 'running',
                }
            }
        }]))

        when(app.Stop).execute().thenReturn(Chain([lambda: {'AppName': 'Stopped'}]))
        when(app.Start).execute().thenReturn(Chain([lambda: {'AppName': 'Started'}]))
        action.execute().get()

        verify(common.NodeInfo).execute()
        verify(app.Stop).execute()
        verify(app.Start).execute()

    @verifyInit('AppPauseAction', {'host': '', 'port': '', 'name': 'AppName', 'profile': 'NewProfile'})
    @verifyInit('AppStartAction', {'host': '', 'port': '', 'name': 'AppName', 'profile': 'NewProfile'})
    def test_AppRestartActionAppIsNotRunningProfileIsSpecified(self):
        node = mock()
        action = app.Restart(node, **{'name': 'AppName', 'profile': 'NewProfile', 'host': '', 'port': ''})
        when(common.NodeInfo).execute().thenReturn(Chain([lambda: {
            'apps': {}
        }]))

        when(app.Stop).execute().thenReturn(Chain([lambda: {'AppName': 'NotRunning'}]))
        when(app.Start).execute().thenReturn(Chain([lambda: {'AppName': 'Started'}]))
        action.execute().get()

        verify(common.NodeInfo).execute()
        verify(app.Stop).execute()
        verify(app.Start).execute()

    @verifyInit('AppPauseAction', {'host': '', 'port': '', 'name': 'AppName', 'profile': 'NewProfile'})
    @verifyInit('AppStartAction', {'host': '', 'port': '', 'name': 'AppName', 'profile': 'NewProfile'})
    def test_AppRestartActionAppIsNotRunningProfileIsNotSpecified(self):
        node = mock()
        action = app.Restart(node, **{'name': 'AppName', 'host': '', 'port': ''})
        when(common.NodeInfo).execute().thenReturn(Chain([lambda: {
            'apps': {}
        }]))

        when(app.Stop).execute().thenReturn(Chain([lambda: {'AppName': 'NotRunning'}]))
        when(app.Start).execute().thenReturn(Chain([lambda: {'AppName': 'Started'}]))
        self.assertRaises(ToolsError, action.execute().get)

        verify(common.NodeInfo).execute()


class ProfileTestCase(unittest.TestCase):
    def tearDown(self):
        unstub()

    def test_ProfileListAction(self):
        storage = mock()
        action = profile.List(storage)
        when(storage).find(any(str), any(tuple)).thenReturn(Chain([lambda: 'Ok']))
        action.execute().get()

        verify(storage).find('profiles', PROFILES_TAGS)

    def test_ProfileViewActionValueErrors(self):
        storage = mock()
        self.assertRaises(ValueError, profile.View, storage, **{})
        self.assertRaises(ValueError, profile.View, storage, **{'profile': ''})

    def test_ProfileViewAction(self):
        storage = mock()
        action = profile.View(storage, **{'name': 'ProfileName'})
        when(storage).read(any(str), any(str)).thenReturn(Chain([lambda: 'Ok']))
        action.execute().get()

        verify(storage).read('profiles', 'ProfileName')

    def test_ProfileUploadActionValueErrors(self):
        storage = mock()
        self.assertRaises(ValueError, profile.Upload, storage, **{})
        self.assertRaises(ValueError, profile.Upload, storage, **{'name': '', 'manifest': 'P'})
        self.assertRaises(ValueError, profile.Upload, storage, **{'name': 'N', 'manifest': ''})

    def test_ProfileUploadAction(self):
        storage = mock()
        jsonEncoder = mock()
        action = profile.Upload(storage, **{'name': 'ProfileName', 'manifest': 'p.json'})
        action.jsonEncoder = jsonEncoder
        when(jsonEncoder).encode('p.json').thenReturn('{-encodedJson-}')
        when(storage).write(any(str), any(str), any(str), any(tuple)).thenReturn(Chain([lambda: 'Ok']))
        action.execute().get()

        verify(storage).write('profiles', 'ProfileName', '{-encodedJson-}', PROFILES_TAGS)

    #todo: Отсюда и выше проверить тестами код на проброс или обработку ошибок
    def test_ProfileUploadActionRethrowsExceptions(self):
        storage = mock()
        jsonEncoder = mock()
        action = profile.Upload(storage, **{'name': 'ProfileName', 'manifest': 'p.json'})
        action.jsonEncoder = jsonEncoder
        when(jsonEncoder).encode('p.json').thenRaise(ValueError)
        self.assertRaises(ValueError, action.execute)

    def test_ProfileRemoveActionValueErrors(self):
        storage = mock()
        self.assertRaises(ValueError, profile.Remove, storage, **{})
        self.assertRaises(ValueError, profile.Remove, storage, **{'name': ''})

    def test_ProfileRemoveAction(self):
        storage = mock()
        action = profile.Remove(storage, **{'name': 'ProfileName'})
        when(storage).remove(any(str), any(str)).thenReturn(Chain([lambda: 'Ok']))
        action.execute().get()

        verify(storage).remove('profiles', 'ProfileName')

    def test_ProfileRemoveActionRethrowsExceptions(self):
        storage = mock()
        action = profile.Remove(storage, **{'name': 'ProfileName'})
        when(storage).remove(any(str), any(str)).thenRaise(Exception)
        self.assertRaises(Exception, action.execute)


class RunlistTestCase(unittest.TestCase):
    def tearDown(self):
        unstub()

    def test_RunlistListAction(self):
        storage = mock()
        action = runlist.List(storage)
        when(storage).find(any(str), any(tuple)).thenReturn(Chain([lambda: 'Ok']))
        action.execute().get()

        verify(storage).find('runlists', RUNLISTS_TAGS)

    def test_RunlistViewActionValueErrors(self):
        storage = mock()
        self.assertRaises(ValueError, runlist.View, storage, **{})
        self.assertRaises(ValueError, runlist.View, storage, **{'name': ''})

    def test_RunlistViewAction(self):
        storage = mock()
        action = runlist.View(storage, **{'name': 'RunlistName'})
        when(storage).read(any(str), any(str)).thenReturn(Chain([lambda: 'Ok']))
        action.execute().get()

        verify(storage).read('runlists', 'RunlistName')

    def test_RunlistUploadActionValueErrors(self):
        storage = mock()
        self.assertRaises(ValueError, runlist.Upload, storage, **{'name': 'R', 'manifest': ''})
        self.assertRaises(ValueError, runlist.Upload, storage, **{'name': '', 'manifest': 'M'})
        self.assertRaises(ValueError, runlist.Upload, storage, **{'name': 'R', 'manifest': '', 'runlist-raw': ''})

    def test_RunlistUploadAction(self):
        storage = mock()
        jsonEncoder = mock()
        action = runlist.Upload(storage, **{'name': 'RunlistName', 'manifest': 'r.json'})
        action.jsonEncoder = jsonEncoder
        when(jsonEncoder).encode('r.json').thenReturn('{-encodedJson-}')
        when(storage).write(any(str), any(str), any(str), any(tuple)).thenReturn(Chain([lambda: 'Ok']))
        action.execute().get()

        verify(storage).write('runlists', 'RunlistName', '{-encodedJson-}', RUNLISTS_TAGS)

    def test_RunlistUploadActionRawRunlistProvided(self):
        storage = mock()
        action = runlist.Upload(storage, **{'name': 'RunlistName', 'runlist-raw': '{raw-data}'})
        when(storage).write(any(str), any(str), any(str), any(tuple)).thenReturn(Chain([lambda: 'Ok']))
        action.execute().get()

        verify(storage).write('runlists', 'RunlistName', msgpack.dumps('{raw-data}'), RUNLISTS_TAGS)

    def test_RunlistRemoveActionValueErrors(self):
        storage = mock()
        self.assertRaises(ValueError, runlist.Remove, storage, **{})
        self.assertRaises(ValueError, runlist.Remove, storage, **{'name': ''})

    def test_RunlistRemoveAction(self):
        storage = mock()
        action = runlist.Remove(storage, **{'name': 'RunlistName'})
        when(storage).remove(any(str), any(str)).thenReturn(Chain([lambda: 'Ok']))
        action.execute().get()

        verify(storage).remove('runlists', 'RunlistName')

    def test_RunlistAddAppActionValueErrors(self):
        storage = mock()
        self.assertRaises(ValueError, runlist.AddApplication, storage, **{})
        self.assertRaises(ValueError, runlist.AddApplication, storage,
                          **{'name': '', 'profile': 'P', 'app': 'A'})
        self.assertRaises(ValueError, runlist.AddApplication, storage,
                          **{'name': 'N', 'profile': '', 'app': 'A'})
        self.assertRaises(ValueError, runlist.AddApplication, storage,
                          **{'name': 'N', 'profile': 'P', 'app': ''})

    def test_RunlistAddAppAction(self):
        storage = mock()
        action = runlist.AddApplication(storage, **{'name': 'RunlistName', 'app': 'App', 'profile': 'Profile'})
        when(runlist.View).execute().thenReturn(msgpack.dumps({
            'App': 'Profile'
        }))
        when(runlist.Upload).execute().thenReturn('Ok')
        action.execute().get()

        verify(runlist.View).execute()
        verify(runlist.Upload).execute()


class CrashlogTestCase(unittest.TestCase):
    def tearDown(self):
        unstub()

    def test_CrashlogListActionValueErrors(self):
        storage = mock()
        self.assertRaises(ValueError, crashlog.List, storage, **{})
        self.assertRaises(ValueError, crashlog.List, storage, **{'name': ''})

    def test_CrashlogListAction(self):
        storage = mock()
        action = crashlog.List(storage, **{'name': 'CrashlogName'})
        when(storage).find(any(str), any(tuple)).thenReturn(Chain([lambda: 'Ok']))
        action.execute().get()

        verify(storage).find('crashlogs', ('CrashlogName', ))

    def test_CrashlogViewActionValueErrors(self):
        storage = mock()
        self.assertRaises(ValueError, crashlog.View, storage, **{})
        self.assertRaises(ValueError, crashlog.View, storage, **{'name': '', 'manifest': 'T'})

    def test_CrashlogViewAction(self):
        storage = mock()
        action = crashlog.View(storage, **{'name': 'AppName', 'manifest': '10000'})
        when(storage).find(any(str), any(tuple)).thenReturn([
            '10000:hash1',
            '20000:hash2'
        ])
        when(storage).read(any(str), any(str)).thenReturn('content')
        action.execute().get()

        verify(storage).find('crashlogs', ('AppName',))
        verify(storage).read('crashlogs', '10000:hash1')

    def test_CrashlogViewActionWithColonNamedApps(self):
        storage = mock()
        action = crashlog.View(storage, **{'name': 'AppName', 'manifest': '10000'})
        when(storage).find(any(str), any(tuple)).thenReturn([
            '10000::appName',
            '10000:app:name',
            '10000:appName:'
        ])
        when(storage).read(any(str), any(str)).thenReturn('content')
        action.execute().get()

        verify(storage).find('crashlogs', ('AppName',))
        verify(storage).read('crashlogs', '10000::appName')
        verify(storage).read('crashlogs', '10000:app:name')
        verify(storage).read('crashlogs', '10000:appName:')

    def test_CrashlogViewActionWithoutTimestampSpecified(self):
        storage = mock()
        action = crashlog.View(storage, **{'name': 'AppName', 'manifest': ''})
        when(storage).find(any(str), any(tuple)).thenReturn([
            '10000:hash1',
            '20000:hash2'
        ])
        when(storage).read(any(str), any(str)).thenReturn('content')
        action.execute().get()

        verify(storage).find('crashlogs', ('AppName',))
        verify(storage).read('crashlogs', '10000:hash1')
        verify(storage).read('crashlogs', '20000:hash2')

    def test_CrashlogRemoveActionValueErrors(self):
        storage = mock
        self.assertRaises(ValueError, crashlog.Remove, storage, **{})
        self.assertRaises(ValueError, crashlog.Remove, storage, **{'name': ''})
        crashlog.Remove(storage, **{'name': 'N', 'manifest': ''})

    def test_CrashlogRemoveAction(self):
        storage = mock()
        action = crashlog.Remove(storage, **{'name': 'AppName', 'manifest': '10000'})
        when(storage).find(any(str), any(tuple)).thenReturn([
            '10000:hash1',
            '20000:hash2'
        ])
        when(storage).remove(any(str), any(str)).thenReturn('Ok')
        action.execute().get()

        verify(storage).find('crashlogs', ('AppName',))
        verify(storage).remove('crashlogs', '10000:hash1')

    def test_CrashlogRemoveActionWithoutTimestampSpecified(self):
        storage = mock()
        action = crashlog.Remove(storage, **{'name': 'AppName', 'manifest': ''})
        when(storage).find(any(str), any(tuple)).thenReturn([
            '10000:hash1',
            '20000:hash2'
        ])
        when(storage).remove(any(str), any(str)).thenReturn('Ok')
        action.execute().get()

        verify(storage).find('crashlogs', ('AppName',))
        verify(storage).remove('crashlogs', '10000:hash1')
        verify(storage).remove('crashlogs', '20000:hash2')

    def test_CrashlogRemoveAllActionValueErrors(self):
        storage = mock()
        self.assertRaises(ValueError, crashlog.RemoveAll, storage, **{})
        self.assertRaises(ValueError, crashlog.RemoveAll, storage, **{'name': ''})

    def test_CrashlogRemoveAll(self):
        storage = mock()
        action = crashlog.RemoveAll(storage, **{'name': 'AppName'})
        when(storage).find(any(str), any(tuple)).thenReturn([
            '10000:hash1',
            '20000:hash2'
        ])
        when(storage).remove(any(str), any(str)).thenReturn('Ok')
        action.execute().get()

        verify(storage).find('crashlogs', ('AppName',))
        verify(storage).remove('crashlogs', '10000:hash1')
        verify(storage).remove('crashlogs', '20000:hash2')


class NodeTestCase(unittest.TestCase):
    def tearDown(self):
        unstub()

    def test_CallValueErrors(self):
        node = mock()
        self.assertRaises(ValueError, common.Call, node, **{})
        self.assertRaises(ValueError, common.Call, node, **{'command': ''})

    def test_CallActionThrowsExceptionWhenServiceIsNotAvailable(self):
        node = mock()
        action = common.Call(node, **{'command': 'Service'})
        self.assertRaises(ServiceCallError, action.execute().get)

    def test_CallActionReturnsApiWhenMethodIsNotSpecified(self):
        node = mock()
        service = mock()
        service._service_api = {
            0: 'method_0',
            1: 'method_1'
        }
        when(common.Call).getService().thenReturn(service)
        action = common.Call(node, **{'command': 'Service'})
        actual = action.execute().get()

        expected = {
            'service': 'Service',
            'request': 'api',
            'response': {
                0: 'method_0',
                1: 'method_1'
            }
        }
        self.assertEqual(expected, actual)

    def test_CallActionThrowsExceptionWhenMethodIsWrong(self):
        node = mock()
        service = mock()
        service._service_api = {
            0: 'method_0',
            1: 'method_1'
        }
        when(common.Call).getService().thenReturn(service)
        action = common.Call(node, **{'command': 'Service.method'})
        self.assertRaises(ServiceError, action.execute().get)

    def test_CallAction(self):
        node = mock()
        service = mock()
        method = mock()
        callableMethod = CallableMock(method)

        service._service_api = {
            0: 'method_0',
            1: 'method_1'
        }
        when(common.Call).getService().thenReturn(service)
        when(common.Call).getMethod(any(object)).thenReturn(callableMethod)

        action = common.Call(node, **{
            'command': "Service.method_0(1, 2, {'key': 'value'})"
        })
        when(method).__call__(1, 2, {'key': 'value'}).thenReturn('Ok')
        action.execute().get()

        verify(method).__call__(1, 2, {'key': 'value'})

    def test_CallActionParser(self):
        node = mock()

        action = common.Call(node, **{'command': 'S.m()'})
        self.assertEqual((), action.parseArguments())

        action = common.Call(node, **{'command': 'S.m(1)'})
        self.assertEqual((1,), action.parseArguments())

        action = common.Call(node, **{'command': 'S.m(1, 2)'})
        self.assertEqual((1, 2), action.parseArguments())

        action = common.Call(node, **{'command': 'S.m("string")'})
        self.assertEqual(('string',), action.parseArguments())

        action = common.Call(node, **{'command': 'S.m((1, 2))'})
        self.assertEqual((1, 2), action.parseArguments())

        action = common.Call(node, **{'command': 'S.m([1, 2])'})
        self.assertEqual(([1, 2],), action.parseArguments())

        action = common.Call(node, **{'command': 'S.m({1: 2})'})
        self.assertEqual(({1: 2},), action.parseArguments())

        action = common.Call(node, **{'command': "S.m({'Echo': 'EchoProfile'})"})
        self.assertEqual(({'Echo': 'EchoProfile'},), action.parseArguments())

        action = common.Call(node, **{'command': 'S.m(True, False)'})
        self.assertEqual((True, False), action.parseArguments())

        action = common.Call(node, **{'command': "S.m(1, 2, {'key': 'value'})"})
        self.assertEqual((1, 2, {'key': 'value'}), action.parseArguments())

        action = common.Call(node, **{'command': "S.m(1, 2, (3, 4), [5, 6], {'key': 'value'})"})
        self.assertEqual((1, 2, (3, 4), [5, 6], {'key': 'value'}), action.parseArguments())

    def test_CallActionThrowsExceptionWhenWrongArgsSyntax(self):
        node = mock()
        service = mock()
        method = mock()
        callableMethod = CallableMock(method)

        service._service_api = {
            0: 'method_0',
            1: 'method_1'
        }
        when(common.Call).getService().thenReturn(service)
        when(common.Call).getMethod(any(object)).thenReturn(callableMethod)

        action = common.Call(node, **{'command': 'S.M(WrongArgs)'})
        self.assertRaises(ServiceCallError, action.execute().get)

    def test_CallActionWhenArgumentsIsNotNecessary(self):
        node = mock()
        service = mock()
        method = mock()
        callableMethod = CallableMock(method)

        service._service_api = {
            0: 'method_0',
            1: 'method_1'
        }
        when(common.Call).getService().thenReturn(service)
        when(common.Call).getMethod(any(object)).thenReturn(callableMethod)

        action = common.Call(node, **{'command': "S.M()"})
        when(method).__call__().thenReturn('Ok')
        action.execute().get()

        verify(method).__call__()


if __name__ == '__main__':
    unittest.main()
