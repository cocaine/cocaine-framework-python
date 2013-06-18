import errno
import socket
from cocaine.services import Service
from time import time
from cocaine.exceptions import CocaineError, ConnectionRefusedError, ConnectionError
from cocaine.tools.tools import (parseCrashlogs,
                                NodeInfoAction,
                                AppRestartAction,
                                AppCheckAction,
                                AppListAction,
                                AppViewAction,
                                AppUploadAction,
                                AppRemoveAction,
                                AppStartAction,
                                AppPauseAction,
                                ProfileListAction,
                                ProfileUploadAction,
                                ProfileViewAction,
                                ProfileRemoveAction,
                                RunlistListAction,
                                RunlistViewAction,
                                RunlistUploadAction,
                                RunlistRemoveAction,
                                RunlistAddApplicationAction,
                                CrashlogRemoveAction,
                                CrashlogRemoveAllAction,
                                CrashlogListAction,
                                CrashlogViewAction,
                                ToolsError)
import json
import msgpack
import sys
from tornado.ioloop import IOLoop

__author__ = 'EvgenySafronov <division494@gmail.com>'


class COLORED:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'

    def disable(self):
        self.HEADER = ''
        self.OKBLUE = ''
        self.OKGREEN = ''
        self.WARNING = ''
        self.FAIL = ''
        self.ENDC = ''
coloredOutput = COLORED()


def printError(message):
    sys.stderr.write('{s}{message}{e}\n'.format(s=coloredOutput.FAIL, message=message, e=coloredOutput.ENDC))


def AwaitDoneWrapper(onDoneMessage=None, onErrorMessage=None):
    def Patch(cls):
        class Wrapper(cls):
            def execute(self):
                chain = super(Wrapper, self).execute()
                chain.then(self.processResult).run()

            def processResult(self, status):
                try:
                    status.get()
                    print((onDoneMessage or 'Action for "{name}" - done').format(name=self.name))
                except Exception as err:
                    printError((onErrorMessage or 'Error occurred on action for "{name}": {error}').format(
                        name=self.name, error=err)
                    )
                finally:
                    IOLoop.instance().stop()
        return Wrapper
    return Patch


def AwaitJsonWrapper(onErrorMessage=None, unpack=False):
    def Patch(cls):
        class Wrapper(cls):
            def execute(self):
                chain = super(Wrapper, self).execute()
                chain.then(self.processResult).run()

            def processResult(self, chunk):
                try:
                    result = chunk.get()
                    if unpack:
                        result = msgpack.loads(result)
                    print(json.dumps(result, indent=4))
                except Exception as err:
                    printError((onErrorMessage or 'Error occurred: {0}').format(err))
                finally:
                    IOLoop.instance().stop()
        return Wrapper
    return Patch


class ConsoleAddApplicationToRunlistAction(RunlistAddApplicationAction):
    def execute(self):
        super(ConsoleAddApplicationToRunlistAction, self).execute().then(self.printResult).run()

    def printResult(self, result):
        try:
            result.get()
            MESSAGE = 'Application "{app}" with profile "{profile}" has been successfully added to runlist "{runlist}"'
            print(MESSAGE.format(app=self.app, profile=self.profile, runlist=self.name))
        except Exception as err:
            printError(err)
        finally:
            IOLoop.instance().stop()


class PrettyPrintableCrashlogListAction(CrashlogListAction):
    def execute(self):
        chain = super(PrettyPrintableCrashlogListAction, self).execute()
        chain.then(self.handleResult).run()

    def handleResult(self, result):
        try:
            print('Currently available crashlogs for application \'%s\'' % self.name)
            for item in parseCrashlogs(result.get()):
                print ' '.join(item)
        except Exception as err:
            printError(('' or 'Unable to view "{name}" - {error}').format(name=self.name, error=err))
        finally:
            IOLoop.instance().stop()


class PrettyPrintableCrashlogViewAction(CrashlogViewAction):
    def execute(self):
        super(PrettyPrintableCrashlogViewAction, self).execute().then(self.handleResult).run()

    def handleResult(self, result):
        try:
            print('Crashlog:')
            print('\n'.join(msgpack.loads(result.get())))
        except Exception as err:
            printError(err)
        finally:
            IOLoop.instance().stop()


def makePrettyCrashlogRemove(cls, onDoneMessage=None):
    class PrettyWrapper(cls):
        def __init__(self, storage=None, **config):
            super(PrettyWrapper, self).__init__(storage, **config)

        def execute(self):
            super(PrettyWrapper, self).execute().then(self.handleResult).run()

        def handleResult(self, result):
            try:
                result.get()
                print((onDoneMessage or 'Action for app "{0}" finished').format(self.name))
            except Exception as err:
                printError(err)
            finally:
                IOLoop.instance().stop()

    return PrettyWrapper


APP_LIST_SUCCESS = 'Currently uploaded apps:'
APP_UPLOAD_SUCCESS = 'The app "{name}" has been successfully uploaded'
APP_UPLOAD_FAIL = 'Unable to upload application {name} - {error}'
APP_REMOVE_SUCCESS = 'The app "{name}" has been successfully removed'
APP_REMOVE_FAIL = 'Unable to remove application {name} - {error}'

PROFILE_LIST_SUCCESS = 'Currently uploaded profiles:'
PROFILE_UPLOAD_SUCCESS = 'The profile "{name}" has been successfully uploaded'
PROFILE_UPLOAD_FAIL = 'Unable to upload profile "{name}" - {error}'
PROFILE_REMOVE_SUCCESS = 'The profile "{name}" has been successfully removed'
PROFILE_REMOVE_FAIL = 'Unable to remove profile "{name}" - {error}'

RUNLIST_LIST_SUCCESS = 'Currently uploaded runlists:'
RUNLIST_UPLOAD_SUCCESS = 'The runlist "{name}" has been successfully uploaded'
RUNLIST_UPLOAD_FAIL = 'Unable to upload runlist "{name}" - {error}'
RUNLIST_REMOVE_SUCCESS = 'The runlist "{name}" has been successfully removed'
RUNLIST_REMOVE_FAIL = 'Unable to remove runlist "{name}" - {error}'

CRASHLOG_REMOVE_SUCCESS = 'Crashlog for app "{0}" have been removed'
CRASHLOGS_REMOVE_SUCCESS = 'Crashlogs for app "{0}" have been removed'

AVAILABLE_TOOLS_ACTIONS = {
    'app:list': AwaitJsonWrapper()(AppListAction),
    'app:view': AwaitJsonWrapper(unpack=True)(AppViewAction),
    'app:upload': AwaitDoneWrapper(APP_UPLOAD_SUCCESS, APP_UPLOAD_FAIL)(AppUploadAction),
    'app:remove': AwaitDoneWrapper(APP_REMOVE_SUCCESS, APP_REMOVE_FAIL)(AppRemoveAction),
    'profile:list': AwaitJsonWrapper()(ProfileListAction),
    'profile:view': AwaitJsonWrapper(unpack=True)(ProfileViewAction),
    'profile:upload': AwaitDoneWrapper(PROFILE_UPLOAD_SUCCESS, PROFILE_UPLOAD_FAIL)(ProfileUploadAction),
    'profile:remove': AwaitDoneWrapper(PROFILE_REMOVE_SUCCESS, PROFILE_REMOVE_FAIL)(ProfileRemoveAction),
    'runlist:list': AwaitJsonWrapper()(RunlistListAction),
    'runlist:view': AwaitJsonWrapper(unpack=True)(RunlistViewAction),
    'runlist:upload': AwaitDoneWrapper(RUNLIST_UPLOAD_SUCCESS, RUNLIST_UPLOAD_FAIL)(RunlistUploadAction),
    'runlist:remove': AwaitDoneWrapper(RUNLIST_REMOVE_SUCCESS, RUNLIST_REMOVE_FAIL)(RunlistRemoveAction),
    'runlist:add-app': AwaitJsonWrapper()(RunlistAddApplicationAction),
    'crashlog:list': PrettyPrintableCrashlogListAction,
    'crashlog:view': PrettyPrintableCrashlogViewAction,
    'crashlog:remove': makePrettyCrashlogRemove(CrashlogRemoveAction, CRASHLOG_REMOVE_SUCCESS),
    'crashlog:removeall': makePrettyCrashlogRemove(CrashlogRemoveAllAction, CRASHLOGS_REMOVE_SUCCESS)
}

AVAILABLE_NODE_ACTIONS = {
    'info': AwaitJsonWrapper()(NodeInfoAction),
    'app:start': AwaitJsonWrapper()(AppStartAction),
    'app:pause': AwaitJsonWrapper()(AppPauseAction),
    'app:stop': AwaitJsonWrapper()(AppPauseAction),
    'app:restart': AwaitJsonWrapper()(AppRestartAction),
    'app:check': AwaitJsonWrapper()(AppCheckAction)
}


class Executor(object):
    """
    This class represents abstract action executor for specified service 'serviceName' and actions pool
    """
    def __init__(self, serviceName, availableActions):
        self.serviceName = serviceName
        self.availableActions = availableActions
        self.loop = IOLoop.instance()

    def executeAction(self, actionName, **options):
        """
        Tries to create service 'serviceName' gets selected action and (if success) invokes it. If any error is
        occurred, it will be immediately printed to stderr and application exits with return code 1

        :param actionName: action name that must be available for selected service
        :param options: various action configuration
        """
        try:
            service = self.createService(options.get('host'), options.get('port'))

            Action = self.availableActions[actionName]
            action = Action(service, **options)
            action.execute()
            self.loop.add_timeout(time() + options.get('timeout', 1.0), self.timeoutErrorback)
            IOLoop.instance().start()
        except CocaineError as err:
            raise ToolsError(err)
        except ValueError as err:
            raise ToolsError(err)
        except KeyError as err:
            raise ToolsError('Action {0} is not available'.format(err))
        except Exception as err:
            raise ToolsError('Unknown error occurred - {0}'.format(err))

    def createService(self, host, port):
        try:
            service = Service(self.serviceName, host, port)
            return service
        except socket.error as err:
            if err.errno == errno.ECONNREFUSED:
                raise ConnectionRefusedError(host, port)
            else:
                raise ConnectionError('Unknown connection error: {0}'.format(err))

    def timeoutErrorback(self):
        printError('Timeout')
        self.loop.stop()


class ToolsExecutor(Executor):
    def __init__(self):
        super(ToolsExecutor, self).__init__('storage', AVAILABLE_TOOLS_ACTIONS)


class NodeExecutor(Executor):
    def __init__(self):
        super(NodeExecutor, self).__init__('node', AVAILABLE_NODE_ACTIONS)