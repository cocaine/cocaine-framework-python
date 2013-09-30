import json
import time

import msgpack
from tornado.ioloop import IOLoop

from cocaine.exceptions import CocaineError, ChokeEvent
from cocaine.tools.actions import common, app, profile, runlist, crashlog
from cocaine.tools.error import Error as ToolsError
from cocaine.tools import log
from cocaine.futures import chain


__author__ = 'EvgenySafronov <division494@gmail.com>'


def AwaitDoneWrapper(onDoneMessage=None, onErrorMessage=None):
    def Patch(cls):
        class Wrapper(cls):
            def execute(self):
                chain = super(Wrapper, self).execute()
                chain.then(self.processResult)
                return chain

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
                    exit(1)
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
                return chain

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
                    exit(1)
                finally:
                    IOLoop.instance().stop()
        return Wrapper
    return Patch


class ConsoleAddApplicationToRunlistAction(runlist.AddApplication):
    def execute(self):
        return super(ConsoleAddApplicationToRunlistAction, self).execute().then(self.printResult).run()

    def printResult(self, result):
        try:
            result.get()
            MESSAGE = 'Application "{app}" with profile "{profile}" has been successfully added to runlist "{runlist}"'
            print(MESSAGE.format(app=self.app, profile=self.profile, runlist=self.name))
        except Exception as err:
            log.error(err)
            exit(1)
        finally:
            IOLoop.instance().stop()


class PrettyPrintableCrashlogListAction(crashlog.List):
    def execute(self):
        chain = super(PrettyPrintableCrashlogListAction, self).execute()
        chain.then(self.handleResult).run()
        return chain

    def handleResult(self, result):
        try:
            crashlogs = result.get()
            print('Currently available crashlogs for application \'%s\'' % self.name)
            for item in crashlog._parseCrashlogs(crashlogs):
                print(' '.join(item))
        except ChokeEvent:
            pass
        except Exception as err:
            log.error(('' or 'Unable to view "{name}" - {error}').format(name=self.name, error=err))
            exit(1)
        finally:
            IOLoop.instance().stop()


class PrettyPrintableCrashlogViewAction(crashlog.View):
    def execute(self):
        return super(PrettyPrintableCrashlogViewAction, self).execute().then(self.handleResult).run()

    def handleResult(self, result):
        try:
            print('Crashlog:')
            print('\n'.join(msgpack.loads(result.get())))
        except Exception as err:
            log.error(err)
            exit(1)
        finally:
            IOLoop.instance().stop()


def makePrettyCrashlogRemove(cls, onDoneMessage=None):
    class PrettyWrapper(cls):
        def __init__(self, storage=None, **config):
            super(PrettyWrapper, self).__init__(storage, **config)

        def execute(self):
            return super(PrettyWrapper, self).execute().then(self.handleResult).run()

        def handleResult(self, result):
            try:
                result.get()
                print((onDoneMessage or 'Action for app "{0}" finished').format(self.name))
            except Exception as err:
                log.error(err)
                exit(1)
            finally:
                IOLoop.instance().stop()

    return PrettyWrapper


class CallActionCli(object):
    def __init__(self, command, host, port, pretty=False):
        self.action = common.Call(command, host, port)
        self.pretty = pretty

    @chain.source
    def execute(self):
        try:
            result = yield self.action.execute()
            requestType = result['request']
            response = result['response']
            if requestType == 'api':
                log.info('Service "{0}" provides following API:'.format(self.action.serviceName))
                log.info('\n'.join(' - {0}'.format(method) for method in response))
            elif requestType == 'invoke':
                if self.pretty:
                    try:
                        response = json.dumps(response, indent=4)
                    except ValueError:
                        log.error('Not valid json')
                log.info(response)
        except Exception as err:
            log.error('Calling failed - %s', err)
            exit(1)
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


AVAILABLE_TOOLS_ACTIONS = {
    'app:list': AwaitJsonWrapper()(app.List),
    'app:view': AwaitJsonWrapper(unpack=True)(app.View),
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
    'call': CallActionCli,
}


class Tools(object):
    def __init__(self, Action):
        self._Action = Action

    @chain.source
    def execute(self, **config):
        try:
            action = self._Action(**config)
            result = yield action.execute()
            self._processResult(result)
        except (ChokeEvent, StopIteration):
            pass
        except Exception as err:
            log.error(err)
            raise ToolsError(err)
        finally:
            IOLoop.instance().stop()

    def _processResult(self, result):
        pass


NG_ACTIONS = {
    'app:upload-manual': Tools(app.Upload),
    'app:upload': Tools(app.LocalUpload),
    'app:remove': Tools(app.Remove),
    'app:check': Tools(app.Check),
}


class Executor(object):
    """
    This class represents abstract action executor for specified service 'serviceName' and actions pool
    """
    def __init__(self, timeout=None):
        self.timeout = timeout
        self._loop = None

    @property
    def loop(self):
        """Lazy event loop initialization"""
        if self._loop:
            return self._loop
        return IOLoop.current()

    def executeAction(self, actionName, **options):
        """
        Tries to create service 'serviceName' gets selected action and (if success) invokes it. If any error is
        occurred, it will be immediately printed to stderr and application exits with return code 1

        :param actionName: action name that must be available for selected service
        :param options: various action configuration
        """
        try:
            if actionName in NG_ACTIONS:
                action = NG_ACTIONS[actionName]
                c = action.execute(**options)
                print(c)
            else:
                Action = AVAILABLE_TOOLS_ACTIONS[actionName]
                action = Action(**options)
                action.execute()
            if self.timeout is not None:
                self.loop.add_timeout(time.time() + self.timeout, self.timeoutErrorback)
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
        exit(1)
