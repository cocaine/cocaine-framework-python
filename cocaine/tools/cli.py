import json
from time import time

import msgpack
from tornado.ioloop import IOLoop

from cocaine.exceptions import CocaineError, ChokeEvent, ToolsError
from cocaine.futures import chain
from cocaine.tools import log
from cocaine.tools.actions import common, app, profile, runlist, crashlog, serve
from cocaine.tools.actions.app import LocalUpload


__author__ = 'EvgenySafronov <division494@gmail.com>'


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
                    log.error((onErrorMessage or 'Error occurred on action for "{name}": {error}').format(
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
                    log.error((onErrorMessage or 'Error occurred: {0}').format(err))
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
            log.error(err)
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
            for item in crashlog._parseCrashlogs(crashlogs):
                print ' '.join(item)
        except ChokeEvent:
            pass
        except Exception as err:
            print(repr(err))
            log.error(('' or 'Unable to view "{name}" - {error}').format(name=self.name, error=err))
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
            log.error(err)
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
                log.error(err)
            finally:
                IOLoop.instance().stop()

    return PrettyWrapper


class CallActionCli(object):
    def __init__(self, **config):
        self.action = common.Call(**config)
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
            log.error(err)
        finally:
            IOLoop.instance().stop()


APP_LIST_SUCCESS = 'Currently uploaded apps:'
# APP_UPLOAD_SUCCESS = 'The app "{name}" has been successfully uploaded'
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

CRASHLOG_REMOVE_SUCCESS = 'Crashlog for app "{0}" has been removed'
CRASHLOGS_REMOVE_SUCCESS = 'Crashlogs for app "{0}" have been removed'


class AppUploadCliAction(object):
    def __init__(self, storage, **config):
        self.action = LocalUpload(storage, **config)

    def execute(self):
        self.action.execute().then(self.processResult)

    def processResult(self, chunk):
        try:
            chunk.get()
        except ChokeEvent:
            pass
        except Exception as err:
            log.error(err)
        finally:
            IOLoop.instance().stop()


class ServeStartActionCli(object):
    def __init__(self, **config):
        self.action = serve.Start(**config)

    @chain.source
    def execute(self):
        try:
            yield self.action.execute()
        except ChokeEvent:
            pass
        except Exception as err:
            log.error(err)
        finally:
            IOLoop.current().stop()


AVAILABLE_TOOLS_ACTIONS = {
    'app:list': AwaitJsonWrapper()(app.List),
    'app:view': AwaitJsonWrapper(unpack=True)(app.View),
    'app:upload-manual': AwaitDoneWrapper()(app.Upload),
    'app:upload': AppUploadCliAction,
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
    'crashlog:removeall': makePrettyCrashlogRemove(crashlog.RemoveAll, CRASHLOGS_REMOVE_SUCCESS),
    'info': AwaitJsonWrapper()(common.NodeInfo),
    'app:start': AwaitJsonWrapper()(app.Start),
    'app:pause': AwaitJsonWrapper()(app.Stop),
    'app:stop': AwaitJsonWrapper()(app.Stop),
    'app:restart': AwaitJsonWrapper()(app.Restart),
    'app:check': AwaitJsonWrapper()(app.Check),
    'call': CallActionCli,
    'serve:start': ServeStartActionCli
}


class Executor(object):
    """
    This class represents abstract action executor for specified service 'serviceName' and actions pool
    """
    def __init__(self, timeout):
        self.timeout = timeout
        self.loop = IOLoop.current()

    def executeAction(self, actionName, **options):
        """
        Tries to create service 'serviceName' gets selected action and (if success) invokes it. If any error is
        occurred, it will be immediately printed to stderr and application exits with return code 1

        :param actionName: action name that must be available for selected service
        :param options: various action configuration
        """
        try:
            Action = AVAILABLE_TOOLS_ACTIONS[actionName]
            action = Action(**options)
            action.execute()
            self.loop.add_timeout(time() + self.timeout, self.timeoutErrorback)
            self.loop.start()
        except CocaineError as err:
            raise ToolsError(err)
        except ValueError as err:
            raise ToolsError(err)
        except KeyError as err:
            raise ToolsError('Action {0} is not available'.format(err))
        except KeyboardInterrupt:
            log.error('Terminated by user')
            self.loop.stop()
        except Exception as err:
            raise ToolsError('Unknown error occurred - {0}'.format(err))

    def timeoutErrorback(self):
        log.error('Timeout')
        self.loop.stop()