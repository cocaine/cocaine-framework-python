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


class PrettyPrintableCrashlogViewAction(crashlog.View):
    def execute(self):
        return super(PrettyPrintableCrashlogViewAction, self).execute().then(self.handleResult)

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
            return super(PrettyWrapper, self).execute().then(self.handleResult)

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


CRASHLOG_REMOVE_SUCCESS = 'Crashlog for app "{0}" has been removed'
CRASHLOGS_REMOVE_SUCCESS = 'Crashlogs for app "{0}" have been removed'


AVAILABLE_TOOLS_ACTIONS = {
    'crashlog:view': PrettyPrintableCrashlogViewAction,
    'crashlog:remove': makePrettyCrashlogRemove(crashlog.Remove, CRASHLOG_REMOVE_SUCCESS),
    'crashlog:removeall': makePrettyCrashlogRemove(crashlog.RemoveAll, CRASHLOGS_REMOVE_SUCCESS),
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


class PrintJsonTools(Tools):
    def _processResult(self, result):
        print(json.dumps(result, indent=4))


class CrashlogListToolHandler(Tools):
    def _processResult(self, result):
        if not result:
            log.info('Crashlog list is empty')
            return

        log.info('{:^20} {:^26} {:^30}'.format('Timestamp', 'Time', 'UUID'))
        for timestamp, time, uuid in crashlog._parseCrashlogs(result):
            print('{:^20} {:^26} {:^30}'.format(timestamp, time, uuid))


NG_ACTIONS = {
    'info': PrintJsonTools(common.NodeInfo),
    'app:check': Tools(app.Check),
    'app:list': PrintJsonTools(app.List),
    'app:view': PrintJsonTools(app.View),
    'app:remove': Tools(app.Remove),
    'app:upload-manual': Tools(app.Upload),
    'app:upload': Tools(app.LocalUpload),
    'app:start': PrintJsonTools(app.Start),
    'app:pause': PrintJsonTools(app.Stop),
    'app:stop': PrintJsonTools(app.Stop),
    'app:restart': PrintJsonTools(app.Restart),
    'profile:list': PrintJsonTools(profile.List),
    'profile:view': PrintJsonTools(profile.View),
    'profile:upload': Tools(profile.Upload),
    'profile:remove': Tools(profile.Remove),
    'runlist:list': PrintJsonTools(runlist.List),
    'runlist:view': PrintJsonTools(runlist.View),
    'runlist:add-app': PrintJsonTools(runlist.AddApplication),
    'runlist:create': Tools(runlist.Create),
    'runlist:upload': Tools(runlist.Upload),
    'runlist:remove': Tools(runlist.Remove),
    'crashlog:list': CrashlogListToolHandler(crashlog.List),
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
            self._loop = IOLoop.current()
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
            assert actionName in dict(NG_ACTIONS, **AVAILABLE_TOOLS_ACTIONS), 'wrong action - {0}'.format(actionName)
            if actionName in NG_ACTIONS:
                action = NG_ACTIONS[actionName]
                action.execute(**options)
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
        except KeyboardInterrupt:
            log.error('Terminated by user')
            self.loop.stop()
        except Exception as err:
            raise ToolsError('Unknown error occurred - {0}'.format(err))

    def timeoutErrorback(self):
        log.error('Timeout')
        self.loop.stop()
        exit(1)
