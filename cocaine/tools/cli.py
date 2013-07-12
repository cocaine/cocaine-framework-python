import json
import msgpack
import sys
import errno
import socket
import logging
from time import time

from tornado.ioloop import IOLoop

from cocaine.tools.actions import common, app, profile, runlist, crashlog
from cocaine.services import Service
from cocaine.exceptions import CocaineError, ConnectionRefusedError, ConnectionError, ChokeEvent, ToolsError
from cocaine.tools.actions.app import LocalUpload

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
                chain.then(self.processResult)

            def processResult(self, status):
                try:
                    status.get()
                    print((onDoneMessage or 'Action for "{name}" - done').format(name=self.name))
                except ChokeEvent:
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
                except ChokeEvent:
                    pass
                except Exception as err:
                    printError((onErrorMessage or 'Error occurred: {0}').format(err))
                finally:
                    IOLoop.instance().stop()
        return Wrapper
    return Patch


class ConsoleAddApplicationToRunlistAction(runlist.AddApplication):
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


class PrettyPrintableCrashlogListAction(crashlog.List):
    def execute(self):
        chain = super(PrettyPrintableCrashlogListAction, self).execute()
        chain.then(self.handleResult).run()

    def handleResult(self, result):
        try:
            crashlogs = result.get()
            print('Currently available crashlogs for application \'%s\'' % self.name)
            for item in crashlog.parseCrashlogs(crashlogs):
                print ' '.join(item)
        except ChokeEvent:
            pass
        except Exception as err:
            print(repr(err))
            printError(('' or 'Unable to view "{name}" - {error}').format(name=self.name, error=err))
        finally:
            IOLoop.instance().stop()


class PrettyPrintableCrashlogViewAction(crashlog.View):
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


class CallActionCli(object):
    def __init__(self, node=None, **config):
        self.action = common.Call(node, **config)
        self.config = config

    def execute(self):
        try:
            result = self.action.execute().get(timeout=1.0)
            requestType = result['request']
            response = result['response']
            if requestType == 'api':
                print('API of service "{0}": {1}'.format(
                    result['service'],
                    json.dumps([method for method in response.values()], indent=4))
                )
            elif requestType == 'invoke':
                print(response)
        except Exception as err:
            printError(err)
        finally:
            IOLoop.instance().stop()


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
RUNLIST_CREATE_SUCCESS = 'The runlist "{name}" has been successfully created'
RUNLIST_CREATE_FAIL = 'Unable to create runlist "{name}" - {error}'
RUNLIST_REMOVE_SUCCESS = 'The runlist "{name}" has been successfully removed'
RUNLIST_REMOVE_FAIL = 'Unable to remove runlist "{name}" - {error}'

CRASHLOG_REMOVE_SUCCESS = 'Crashlog for app "{0}" have been removed'
CRASHLOGS_REMOVE_SUCCESS = 'Crashlogs for app "{0}" have been removed'


class AppUpload2CliAction(object):
    def __init__(self, storage, **config):
        self.action = LocalUpload(storage, **config)

    def execute(self):
        self.action.execute().then(self.processResult)

    def processResult(self, chunk):
        try:
            result = chunk.get()
            print(result)
        except ChokeEvent:
            pass
        except Exception as err:
            printError(err)
        finally:
            IOLoop.instance().stop()


AVAILABLE_TOOLS_ACTIONS = {
    'app:list': AwaitJsonWrapper()(app.List),
    'app:view': AwaitJsonWrapper(unpack=True)(app.View),
    'app:upload': AwaitDoneWrapper(APP_UPLOAD_SUCCESS, APP_UPLOAD_FAIL)(app.Upload),
    'app:upload2': AppUpload2CliAction,
    'app:remove': AwaitDoneWrapper(APP_REMOVE_SUCCESS, APP_REMOVE_FAIL)(app.Remove),
    'profile:list': AwaitJsonWrapper()(profile.List),
    'profile:view': AwaitJsonWrapper(unpack=True)(profile.View),
    'profile:upload': AwaitDoneWrapper(PROFILE_UPLOAD_SUCCESS, PROFILE_UPLOAD_FAIL)(profile.Upload),
    'profile:remove': AwaitDoneWrapper(PROFILE_REMOVE_SUCCESS, PROFILE_REMOVE_FAIL)(profile.Remove),
    'runlist:list': AwaitJsonWrapper()(runlist.List),
    'runlist:view': AwaitJsonWrapper(unpack=True)(runlist.View),
    'runlist:upload': AwaitDoneWrapper(RUNLIST_UPLOAD_SUCCESS, RUNLIST_UPLOAD_FAIL)(runlist.Upload),
    'runlist:create': AwaitDoneWrapper(RUNLIST_CREATE_SUCCESS, RUNLIST_CREATE_FAIL)(runlist.Create),
    'runlist:remove': AwaitDoneWrapper(RUNLIST_REMOVE_SUCCESS, RUNLIST_REMOVE_FAIL)(runlist.Remove),
    'runlist:add-app': AwaitJsonWrapper()(runlist.AddApplication),
    'crashlog:list': PrettyPrintableCrashlogListAction,
    'crashlog:view': PrettyPrintableCrashlogViewAction,
    'crashlog:remove': makePrettyCrashlogRemove(crashlog.Remove, CRASHLOG_REMOVE_SUCCESS),
    'crashlog:removeall': makePrettyCrashlogRemove(crashlog.RemoveAll, CRASHLOGS_REMOVE_SUCCESS)
}

AVAILABLE_NODE_ACTIONS = {
    'info': AwaitJsonWrapper()(common.NodeInfo),
    'call': CallActionCli,
    'app:start': AwaitJsonWrapper()(app.Start),
    'app:pause': AwaitJsonWrapper()(app.Stop),
    'app:stop': AwaitJsonWrapper()(app.Stop),
    'app:restart': AwaitJsonWrapper()(app.Restart),
    'app:check': AwaitJsonWrapper()(app.Check)
}


class Executor(object):
    """
    This class represents abstract action executor for specified service 'serviceName' and actions pool
    """
    def __init__(self, serviceName, availableActions, **config):
        self.serviceName = serviceName
        self.availableActions = availableActions
        self.config = config
        self.loop = IOLoop.instance()

        debugLevel = config.get('debug', 'disable')
        if debugLevel != 'disable':
            ch = logging.StreamHandler()
            ch.setLevel(logging.DEBUG)
            formatter = logging.Formatter('%(name)s: %(levelname)-8s: %(message)s')
            ch.setFormatter(formatter)

            logNames = [
                __name__,
                'cocaine.tools.actions.app.AppLocalUploadAction'
            ]
            if debugLevel == 'all':
                logNames.append('cocaine.futures.chain')
                logNames.append('cocaine.testing.mocks')

            for logName in logNames:
                log = logging.getLogger(logName)
                log.setLevel(logging.DEBUG)
                log.propagate = False
                log.addHandler(ch)

    def executeAction(self, actionName, **options):
        """
        Tries to create service 'serviceName' gets selected action and (if success) invokes it. If any error is
        occurred, it will be immediately printed to stderr and application exits with return code 1

        :param actionName: action name that must be available for selected service
        :param options: various action configuration
        """
        try:
            service = self.createService(self.config.get('host'), self.config.get('port'))

            Action = self.availableActions[actionName]
            action = Action(service, **dict(self.config.items() + options.items()))
            action.execute()
            self.loop.add_timeout(time() + self.config.get('timeout'), self.timeoutErrorback)
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


class StorageExecutor(Executor):
    def __init__(self, **config):
        super(StorageExecutor, self).__init__('storage', AVAILABLE_TOOLS_ACTIONS, **config)


class NodeExecutor(Executor):
    def __init__(self, **config):
        super(NodeExecutor, self).__init__('node', AVAILABLE_NODE_ACTIONS, **config)