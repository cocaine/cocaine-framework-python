import json
import time
import errno

import msgpack
from tornado.ioloop import IOLoop

from cocaine.exceptions import ChokeEvent
from cocaine.futures import chain
from cocaine.tools.actions import common, app, profile, runlist, crashlog
from cocaine.tools.error import Error as ToolsError
from cocaine.tools import log


__author__ = 'EvgenySafronov <division494@gmail.com>'


class ToolHandler(object):
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


class JsonToolHandler(ToolHandler):
    def _processResult(self, result):
        print(json.dumps(result, indent=4))


class CrashlogStatusToolHandler(ToolHandler):
    FORMAT_HEADER = '{:^20} {:^26} {:^36}'
    HEADER = FORMAT_HEADER.format('Application', 'Time', 'UUID')
    FORMAT_CONTENT = '{:<20} {:<26} {:<36}'

    def _processResult(self, result):
        if not result:
            print('There are no applications with crashlogs')

        log.info(self.HEADER)
        print('=' * len(self.HEADER))
        for app, (timestamp, time, uuid) in sorted(result, key=lambda (app, (timestamp, time, uuid)): timestamp):
            print(self.FORMAT_CONTENT.format(app, time, uuid))


class CrashlogListToolHandler(ToolHandler):
    FORMAT_HEADER = '{:^20} {:^26} {:^36}'
    HEADER = FORMAT_HEADER.format('Timestamp', 'Time', 'UUID')

    def _processResult(self, result):
        if not result:
            log.info('Crashlog list is empty')
            return

        log.info(self.HEADER)
        for timestamp, time, uuid in sorted(crashlog._parseCrashlogs(result), key=lambda (ts, time, uuid): ts):
            print(self.FORMAT_HEADER.format(timestamp, time, uuid))


class CrashlogViewToolHandler(ToolHandler):
    def _processResult(self, result):
        print('\n'.join(msgpack.loads(result)))


class CallActionCli(ToolHandler):
    def _processResult(self, result):
        requestType = result['request']
        response = result['response']
        if requestType == 'api':
            log.info('Service provides following API:')
            log.info('\n'.join(' - {0}'.format(method) for method in response))
        elif requestType == 'invoke':
            print(response)


NG_ACTIONS = {
    'info': JsonToolHandler(common.NodeInfo),
    'call': CallActionCli(common.Call),

    'app:check': ToolHandler(app.Check),
    'app:list': JsonToolHandler(app.List),
    'app:view': JsonToolHandler(app.View),
    'app:remove': ToolHandler(app.Remove),
    'app:upload-manual': ToolHandler(app.Upload),
    'app:upload': ToolHandler(app.LocalUpload),
    'app:start': JsonToolHandler(app.Start),
    'app:pause': JsonToolHandler(app.Stop),
    'app:stop': JsonToolHandler(app.Stop),
    'app:restart': JsonToolHandler(app.Restart),

    'profile:list': JsonToolHandler(profile.List),
    'profile:view': JsonToolHandler(profile.View),
    'profile:upload': ToolHandler(profile.Upload),
    'profile:remove': ToolHandler(profile.Remove),

    'runlist:list': JsonToolHandler(runlist.List),
    'runlist:view': JsonToolHandler(runlist.View),
    'runlist:add-app': JsonToolHandler(runlist.AddApplication),
    'runlist:create': ToolHandler(runlist.Create),
    'runlist:upload': ToolHandler(runlist.Upload),
    'runlist:remove': ToolHandler(runlist.Remove),

    'crashlog:status': CrashlogStatusToolHandler(crashlog.Status),
    'crashlog:list': CrashlogListToolHandler(crashlog.List),
    'crashlog:view': CrashlogViewToolHandler(crashlog.View),
    'crashlog:remove': ToolHandler(crashlog.Remove),
    'crashlog:removeall': ToolHandler(crashlog.RemoveAll),
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
            assert actionName in NG_ACTIONS, 'wrong action - {0}'.format(actionName)

            action = NG_ACTIONS[actionName]
            action.execute(**options)
            if self.timeout is not None:
                self.loop.add_timeout(time.time() + self.timeout, self.timeoutErrorback)

            self.loop.start()
        finally:
            self.loop.stop()

    def timeoutErrorback(self):
        log.error('Timeout')
        self.loop.stop()
        exit(errno.ETIMEDOUT)
