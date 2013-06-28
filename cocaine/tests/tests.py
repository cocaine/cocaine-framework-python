# coding=utf-8
import unittest
import msgpack
import time
from tornado.ioloop import IOLoop
from tornado.testing import AsyncTestCase
from cocaine.futures import Future
from mockito import mock, when, verify, any, unstub
from cocaine.tools.tools import *
from cocaine.futures.chain import ChainFactory
from cocaine.exceptions import ServiceError


__author__ = 'EvgenySafronov <division494@gmail.com>'


class CallableMock(object):
    def __init__(self, mock):
        self.mock = mock

    def __call__(self, *args, **kwargs):
        return self.mock.__call__(*args, **kwargs)

    def __getattr__(self, methodName):
        return self.mock.__getattr__(methodName)


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

    def test_AppStartActionValueErrors(self):
        node = mock()
        self.assertRaises(ValueError, AppStartAction, node, **{})
        self.assertRaises(ValueError, AppStartAction, node, **{'name': '', 'profile': 'P'})
        self.assertRaises(ValueError, AppStartAction, node, **{'name': 'N', 'profile': ''})

    def test_AppStartAction(self):
        node = mock()
        action = AppStartAction(node, **{'name': 'AppName', 'profile': 'ProfileName'})
        action.execute()

        verify(node).start_app({'AppName': 'ProfileName'})

    def test_AppPauseActionValueErrors(self):
        node = mock()
        self.assertRaises(ValueError, AppPauseAction, node, **{})
        self.assertRaises(ValueError, AppPauseAction, node, **{'name': ''})

    def test_AppPauseAction(self):
        node = mock()
        action = AppPauseAction(node, **{'name': 'AppName'})
        action.execute()

        verify(node).pause_app(['AppName'])

    def test_AppCheckActionValueErrors(self):
        node = mock()
        self.assertRaises(ValueError, AppCheckAction, node, **{})
        self.assertRaises(ValueError, AppCheckAction, node, **{'name': ''})

    def test_AppCheckAction(self):
        node = mock()
        action = AppCheckAction(node, **{'name': 'AppName'})
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
        when(node).info().thenReturn(ChainFactory([lambda: mockInfo]))
        actual = action.execute().get(timeout=0.1)

        verify(node).info()
        self.assertEqual({'AppName': 'running'}, actual)

    def test_AppCheckActionReturnsStoppedOrMissingWhenApplicationIsNotFound(self):
        node = mock()
        action = AppCheckAction(node, **{'name': 'AppName'})
        mockInfo = {
            'apps': {
            }
        }
        when(node).info().thenReturn(ChainFactory([lambda: mockInfo]))
        actual = action.execute().get(timeout=0.1)

        verify(node).info()
        self.assertEqual({'AppName': 'stopped or missing'}, actual)

    def test_AppRestartActionValueErrors(self):
        node = mock()
        self.assertRaises(ValueError, AppRestartAction, node, **{})
        self.assertRaises(ValueError, AppRestartAction, node, **{'name': ''})

    @verifyInit('AppPauseAction', {'host': '', 'port': '', 'name': 'AppName'})
    @verifyInit('AppStartAction', {'host': '', 'port': '', 'name': 'AppName', 'profile': 'ProfileName'})
    def test_AppRestartActionAppIsRunningProfileIsNotSpecified(self):
        node = mock()
        action = AppRestartAction(node, **{'name': 'AppName', 'host': '', 'port': ''})
        when(NodeInfoAction).execute().thenReturn(ChainFactory([lambda: {
            'apps': {
                'AppName': {
                    'profile': 'ProfileName',
                    'state': 'running',
                }
            }
        }]))

        when(AppPauseAction).execute().thenReturn(ChainFactory([lambda: {'AppName': 'Stopped'}]))
        when(AppStartAction).execute().thenReturn(ChainFactory([lambda: {'AppName': 'Started'}]))
        action.execute().get()

        verify(NodeInfoAction).execute()
        verify(AppPauseAction).execute()
        verify(AppStartAction).execute()

    @verifyInit('AppPauseAction', {'host': '', 'port': '', 'name': 'AppName', 'profile': 'NewProfile'})
    @verifyInit('AppStartAction', {'host': '', 'port': '', 'name': 'AppName', 'profile': 'NewProfile'})
    def test_AppRestartActionAppIsRunningProfileIsSpecified(self):
        node = mock()
        action = AppRestartAction(node, **{'name': 'AppName', 'profile': 'NewProfile', 'host': '', 'port': ''})
        when(NodeInfoAction).execute().thenReturn(ChainFactory([lambda: {
            'apps': {
                'AppName': {
                    'profile': 'ProfileName',
                    'state': 'running',
                }
            }
        }]))

        when(AppPauseAction).execute().thenReturn(ChainFactory([lambda: {'AppName': 'Stopped'}]))
        when(AppStartAction).execute().thenReturn(ChainFactory([lambda: {'AppName': 'Started'}]))
        action.execute().get()

        verify(NodeInfoAction).execute()
        verify(AppPauseAction).execute()
        verify(AppStartAction).execute()

    @verifyInit('AppPauseAction', {'host': '', 'port': '', 'name': 'AppName', 'profile': 'NewProfile'})
    @verifyInit('AppStartAction', {'host': '', 'port': '', 'name': 'AppName', 'profile': 'NewProfile'})
    def test_AppRestartActionAppIsNotRunningProfileIsSpecified(self):
        node = mock()
        action = AppRestartAction(node, **{'name': 'AppName', 'profile': 'NewProfile', 'host': '', 'port': ''})
        when(NodeInfoAction).execute().thenReturn(ChainFactory([lambda: {
            'apps': {}
        }]))

        when(AppPauseAction).execute().thenReturn(ChainFactory([lambda: {'AppName': 'NotRunning'}]))
        when(AppStartAction).execute().thenReturn(ChainFactory([lambda: {'AppName': 'Started'}]))
        action.execute().get()

        verify(NodeInfoAction).execute()
        verify(AppPauseAction).execute()
        verify(AppStartAction).execute()

    @verifyInit('AppPauseAction', {'host': '', 'port': '', 'name': 'AppName', 'profile': 'NewProfile'})
    @verifyInit('AppStartAction', {'host': '', 'port': '', 'name': 'AppName', 'profile': 'NewProfile'})
    def test_AppRestartActionAppIsNotRunningProfileIsNotSpecified(self):
        node = mock()
        action = AppRestartAction(node, **{'name': 'AppName', 'host': '', 'port': ''})
        when(NodeInfoAction).execute().thenReturn(ChainFactory([lambda: {
            'apps': {}
        }]))

        when(AppPauseAction).execute().thenReturn(ChainFactory([lambda: {'AppName': 'NotRunning'}]))
        when(AppStartAction).execute().thenReturn(ChainFactory([lambda: {'AppName': 'Started'}]))
        self.assertRaises(ToolsError, action.execute().get)

        verify(NodeInfoAction).execute()


class ProfileTestCase(unittest.TestCase):
    def tearDown(self):
        unstub()

    def test_ProfileListAction(self):
        storage = mock()
        action = ProfileListAction(storage)
        when(storage).find(any(str), any(tuple)).thenReturn(ChainFactory([lambda: 'Ok']))
        action.execute().get()

        verify(storage).find('profiles', PROFILES_TAGS)

    def test_ProfileViewActionValueErrors(self):
        storage = mock()
        self.assertRaises(ValueError, ProfileViewAction, storage, **{})
        self.assertRaises(ValueError, ProfileViewAction, storage, **{'profile': ''})

    def test_ProfileViewAction(self):
        storage = mock()
        action = ProfileViewAction(storage, **{'name': 'ProfileName'})
        when(storage).read(any(str), any(str)).thenReturn(ChainFactory([lambda: 'Ok']))
        action.execute().get()

        verify(storage).read('profiles', 'ProfileName')

    def test_ProfileUploadActionValueErrors(self):
        storage = mock()
        self.assertRaises(ValueError, ProfileUploadAction, storage, **{})
        self.assertRaises(ValueError, ProfileUploadAction, storage, **{'name': '', 'manifest': 'P'})
        self.assertRaises(ValueError, ProfileUploadAction, storage, **{'name': 'N', 'manifest': ''})

    def test_ProfileUploadAction(self):
        storage = mock()
        jsonEncoder = mock()
        action = ProfileUploadAction(storage, **{'name': 'ProfileName', 'manifest': 'p.json'})
        action.jsonEncoder = jsonEncoder
        when(jsonEncoder).encode('p.json').thenReturn('{-encodedJson-}')
        when(storage).write(any(str), any(str), any(str), any(tuple)).thenReturn(ChainFactory([lambda: 'Ok']))
        action.execute().get()

        verify(storage).write('profiles', 'ProfileName', '{-encodedJson-}', PROFILES_TAGS)

    #todo: Отсюда и выше проверить тестами код на проброс или обработку ошибок
    def test_ProfileUploadActionRethrowsExceptions(self):
        storage = mock()
        jsonEncoder = mock()
        action = ProfileUploadAction(storage, **{'name': 'ProfileName', 'manifest': 'p.json'})
        action.jsonEncoder = jsonEncoder
        when(jsonEncoder).encode('p.json').thenRaise(ValueError)
        self.assertRaises(ValueError, action.execute)

    def test_ProfileRemoveActionValueErrors(self):
        storage = mock()
        self.assertRaises(ValueError, ProfileRemoveAction, storage, **{})
        self.assertRaises(ValueError, ProfileRemoveAction, storage, **{'name': ''})

    def test_ProfileRemoveAction(self):
        storage = mock()
        action = ProfileRemoveAction(storage, **{'name': 'ProfileName'})
        when(storage).remove(any(str), any(str)).thenReturn(ChainFactory([lambda: 'Ok']))
        action.execute().get()

        verify(storage).remove('profiles', 'ProfileName')

    def test_ProfileRemoveActionRethrowsExceptions(self):
        storage = mock()
        action = ProfileRemoveAction(storage, **{'name': 'ProfileName'})
        when(storage).remove(any(str), any(str)).thenRaise(Exception)
        self.assertRaises(Exception, action.execute)


class RunlistTestCase(unittest.TestCase):
    def tearDown(self):
        unstub()

    def test_RunlistListAction(self):
        storage = mock()
        action = RunlistListAction(storage)
        when(storage).find(any(str), any(tuple)).thenReturn(ChainFactory([lambda: 'Ok']))
        action.execute().get()

        verify(storage).find('runlists', RUNLISTS_TAGS)

    def test_RunlistViewActionValueErrors(self):
        storage = mock()
        self.assertRaises(ValueError, RunlistViewAction, storage, **{})
        self.assertRaises(ValueError, RunlistViewAction, storage, **{'name': ''})

    def test_RunlistViewAction(self):
        storage = mock()
        action = RunlistViewAction(storage, **{'name': 'RunlistName'})
        when(storage).read(any(str), any(str)).thenReturn(ChainFactory([lambda: 'Ok']))
        action.execute().get()

        verify(storage).read('runlists', 'RunlistName')

    def test_RunlistUploadActionValueErrors(self):
        storage = mock()
        self.assertRaises(ValueError, RunlistUploadAction, storage, **{'name': 'R', 'manifest': ''})
        self.assertRaises(ValueError, RunlistUploadAction, storage, **{'name': '', 'manifest': 'M'})
        self.assertRaises(ValueError, RunlistUploadAction, storage, **{'name': 'R', 'manifest': '', 'runlist-raw': ''})

    def test_RunlistUploadAction(self):
        storage = mock()
        jsonEncoder = mock()
        action = RunlistUploadAction(storage, **{'name': 'RunlistName', 'manifest': 'r.json'})
        action.jsonEncoder = jsonEncoder
        when(jsonEncoder).encode('r.json').thenReturn('{-encodedJson-}')
        when(storage).write(any(str), any(str), any(str), any(tuple)).thenReturn(ChainFactory([lambda: 'Ok']))
        action.execute().get()

        verify(storage).write('runlists', 'RunlistName', '{-encodedJson-}', RUNLISTS_TAGS)

    def test_RunlistUploadActionRawRunlistProvided(self):
        storage = mock()
        action = RunlistUploadAction(storage, **{'name': 'RunlistName', 'runlist-raw': '{raw-data}'})
        when(storage).write(any(str), any(str), any(str), any(tuple)).thenReturn(ChainFactory([lambda: 'Ok']))
        action.execute().get()

        verify(storage).write('runlists', 'RunlistName', msgpack.dumps('{raw-data}'), RUNLISTS_TAGS)

    def test_RunlistRemoveActionValueErrors(self):
        storage = mock()
        self.assertRaises(ValueError, RunlistRemoveAction, storage, **{})
        self.assertRaises(ValueError, RunlistRemoveAction, storage, **{'name': ''})

    def test_RunlistRemoveAction(self):
        storage = mock()
        action = RunlistRemoveAction(storage, **{'name': 'RunlistName'})
        when(storage).remove(any(str), any(str)).thenReturn(ChainFactory([lambda: 'Ok']))
        action.execute().get()

        verify(storage).remove('runlists', 'RunlistName')

    def test_RunlistAddAppActionValueErrors(self):
        storage = mock()
        self.assertRaises(ValueError, RunlistAddApplicationAction, storage, **{})
        self.assertRaises(ValueError, RunlistAddApplicationAction, storage,
                          **{'name': '', 'profile': 'P', 'app': 'A'})
        self.assertRaises(ValueError, RunlistAddApplicationAction, storage,
                          **{'name': 'N', 'profile': '', 'app': 'A'})
        self.assertRaises(ValueError, RunlistAddApplicationAction, storage,
                          **{'name': 'N', 'profile': 'P', 'app': ''})

    def test_RunlistAddAppAction(self):
        storage = mock()
        action = RunlistAddApplicationAction(storage, **{'name': 'RunlistName', 'app': 'App', 'profile': 'Profile'})
        when(RunlistViewAction).execute().thenReturn(msgpack.dumps({
            'App': 'Profile'
        }))
        when(RunlistUploadAction).execute().thenReturn('Ok')
        action.execute().get()

        verify(RunlistViewAction).execute()
        verify(RunlistUploadAction).execute()


class CrashlogTestCase(unittest.TestCase):
    def tearDown(self):
        unstub()

    def test_CrashlogListActionValueErrors(self):
        storage = mock()
        self.assertRaises(ValueError, CrashlogListAction, storage, **{})
        self.assertRaises(ValueError, CrashlogListAction, storage, **{'name': ''})

    def test_CrashlogListAction(self):
        storage = mock()
        action = CrashlogListAction(storage, **{'name': 'CrashlogName'})
        when(storage).find(any(str), any(tuple)).thenReturn(ChainFactory([lambda: 'Ok']))
        action.execute().get()

        verify(storage).find('crashlogs', ('CrashlogName', ))

    def test_CrashlogViewActionValueErrors(self):
        storage = mock()
        self.assertRaises(ValueError, CrashlogViewAction, storage, **{})
        self.assertRaises(ValueError, CrashlogViewAction, storage, **{'name': '', 'manifest': 'T'})

    def test_CrashlogViewAction(self):
        storage = mock()
        action = CrashlogViewAction(storage, **{'name': 'AppName', 'manifest': '10000'})
        when(storage).find(any(str), any(tuple)).thenReturn([
            '10000:hash1',
            '20000:hash2'
        ])
        when(storage).read(any(str), any(str)).thenReturn('content')
        action.execute().get()

        verify(storage).find('crashlogs', ('AppName',))
        verify(storage).read('crashlogs', '10000:hash1')

    def test_CrashlogViewActionWithoutTimestampSpecified(self):
        storage = mock()
        action = CrashlogViewAction(storage, **{'name': 'AppName', 'manifest': ''})
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
        self.assertRaises(ValueError, CrashlogRemoveAction, storage, **{})
        self.assertRaises(ValueError, CrashlogRemoveAction, storage, **{'name': ''})
        CrashlogRemoveAction(storage, **{'name': 'N', 'manifest': ''})

    def test_CrashlogRemoveAction(self):
        storage = mock()
        action = CrashlogRemoveAction(storage, **{'name': 'AppName', 'manifest': '10000'})
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
        action = CrashlogRemoveAction(storage, **{'name': 'AppName', 'manifest': ''})
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
        self.assertRaises(ValueError, CrashlogRemoveAllAction, storage, **{})
        self.assertRaises(ValueError, CrashlogRemoveAllAction, storage, **{'name': ''})

    def test_CrashlogRemoveAll(self):
        storage = mock()
        action = CrashlogRemoveAllAction(storage, **{'name': 'AppName'})
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
        self.assertRaises(ValueError, CallAction, node, **{})
        self.assertRaises(ValueError, CallAction, node, **{'command': ''})

    def test_CallActionThrowsExceptionWhenServiceIsNotAvailable(self):
        node = mock()
        action = CallAction(node, **{'command': 'Service'})
        self.assertRaises(ServiceCallError, action.execute().get)

    def test_CallActionReturnsApiWhenMethodIsNotSpecified(self):
        node = mock()
        service = mock()
        service._service_api = {
            0: 'method_0',
            1: 'method_1'
        }
        when(CallAction).getService().thenReturn(service)
        action = CallAction(node, **{'command': 'Service'})
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
        when(CallAction).getService().thenReturn(service)
        action = CallAction(node, **{'command': 'Service.method'})
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
        when(CallAction).getService().thenReturn(service)
        when(CallAction).getMethod(any(object)).thenReturn(callableMethod)

        action = CallAction(node, **{
            'command': "Service.method_0(1, 2, {'key': 'value'})"
        })
        when(method).__call__(1, 2, {'key': 'value'}).thenReturn('Ok')
        action.execute().get()

        verify(method).__call__(1, 2, {'key': 'value'})

    def test_CallActionParser(self):
        node = mock()

        action = CallAction(node, **{'command': 'S.m()'})
        self.assertEqual((), action.parseArguments())

        action = CallAction(node, **{'command': 'S.m(1)'})
        self.assertEqual((1,), action.parseArguments())

        action = CallAction(node, **{'command': 'S.m(1, 2)'})
        self.assertEqual((1, 2), action.parseArguments())

        action = CallAction(node, **{'command': 'S.m("string")'})
        self.assertEqual(('string',), action.parseArguments())

        action = CallAction(node, **{'command': 'S.m((1, 2))'})
        self.assertEqual((1, 2), action.parseArguments())

        action = CallAction(node, **{'command': 'S.m([1, 2])'})
        self.assertEqual(([1, 2],), action.parseArguments())

        action = CallAction(node, **{'command': 'S.m({1: 2})'})
        self.assertEqual(({1: 2},), action.parseArguments())

        action = CallAction(node, **{'command': "S.m({'Echo': 'EchoProfile'})"})
        self.assertEqual(({'Echo': 'EchoProfile'},), action.parseArguments())

        action = CallAction(node, **{'command': 'S.m(True, False)'})
        self.assertEqual((True, False), action.parseArguments())

        action = CallAction(node, **{'command': "S.m(1, 2, {'key': 'value'})"})
        self.assertEqual((1, 2, {'key': 'value'}), action.parseArguments())

        action = CallAction(node, **{'command': "S.m(1, 2, (3, 4), [5, 6], {'key': 'value'})"})
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
        when(CallAction).getService().thenReturn(service)
        when(CallAction).getMethod(any(object)).thenReturn(callableMethod)

        action = CallAction(node, **{'command': 'S.M(WrongArgs)'})
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
        when(CallAction).getService().thenReturn(service)
        when(CallAction).getMethod(any(object)).thenReturn(callableMethod)

        action = CallAction(node, **{'command': "S.M()"})
        when(method).__call__().thenReturn('Ok')
        action.execute().get()

        verify(method).__call__()


class FutureTestMock(Future):
        def __init__(self, ioLoop, chunks=None, interval=0.1):
            super(FutureTestMock, self).__init__()
            self.ioLoop = ioLoop
            self.chunks = chunks
            self.interval = interval
            self.currentChunkId = 0

        def bind(self, callback, errorback=None, on_done=None):
            self.callback = callback
            self.errorback = errorback
            self.doneback = on_done
            self.start()

        def start(self):
            for pos, value in enumerate(self.chunks):
                self.ioLoop.add_timeout(time.time() + (pos + 1) * self.interval, self.invoke)

        def invoke(self):
            chunk = self.chunks[self.currentChunkId]
            self.currentChunkId += 1
            return self.callback(chunk)


class ServiceMock(object):
    def __init__(self, ioLoop, chunks=None, T=ChainFactory):
        self.ioLoop = ioLoop
        self.T = T
        if not chunks:
            chunks = [None]
        self.chunks = chunks

    def execute(self):
        return self.T([lambda: FutureTestMock(self.ioLoop, self.chunks)])


def multiThenAssert(obj, expected):
    def wrapper(func):
        class decorator(object):
            def __init__(self):
                self.expected = expected
                self.pos = 0

            def __call__(self, r):
                func(self.expected[self.pos], r)
                self.pos += 1
                if self.pos == len(self.expected):
                    obj.stop()
        return decorator()
    return wrapper


class ApiTestCase(AsyncTestCase):
    """
    To test:
        Async API:
            - service -> future(1) => then
            - service -> future(*) => then
            - service -> var(1) => then
            - service -> error(1) => then
            - service -> future + error => then

        Sync API:
            - service -> future(1) => get
            - service -> future(*) => get *
            - service -> future(1,e) => get 1,e

            - service -> future(1) => get, get(e)
    """
    def test_ThenOneAsyncChunk(self):
        @multiThenAssert(self, [1])
        def check(expected, r):
            try:
                self.assertEqual(r.get(), expected)
            except Exception as err:
                print(err)
        s = ServiceMock(self.io_loop, chunks=[1]).execute()
        s.then(check)
        self.wait()

    def test_ThenMultipleAsyncChunks(self):
        @multiThenAssert(self, [1, 2, 3])
        def check(expected, r):
            try:
                self.assertEqual(r.get(), expected)
            except Exception as err:
                print(err)
        s = ServiceMock(self.io_loop, chunks=[1, 2, 3]).execute()
        s.then(check)
        self.wait()

    # def test_ThenOneSyncChunk(self):
    #     @multiThenAssert(self, [1])
    #     def check(expected, r):
    #         try:
    #             self.assertEqual(r.get(), expected)
    #         except Exception as err:
    #             print(err)
    #     s = ChainFactory([lambda: 1])
    #     s.then(check)
    #     self.wait(timeout=0.5)


if __name__ == '__main__':
    unittest.main()
