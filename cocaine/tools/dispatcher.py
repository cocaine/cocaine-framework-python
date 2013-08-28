import logging
import os
import sys

from opster import Dispatcher

from cocaine.exceptions import ToolsError
from cocaine.asio.service import Locator, Service
from cocaine.logging.hanlders import ColoredFormatter, interactiveEmit
from cocaine.tools.actions import proxy
from cocaine.tools.cli import Executor

__author__ = 'Evgeny Safronov <division494@gmail.com>'


DESCRIPTION = ''
DEFAULT_HOST = 'localhost'
DEFAULT_PORT = 10053


class Global(object):
    options = [
        ('h', 'host', DEFAULT_HOST, 'hostname'),
        ('p', 'port', DEFAULT_PORT, 'port'),
        ('', 'timeout', 1.0, 'timeout, s'),
        ('', 'color', True, 'enable colored output'),
        ('', 'debug', ('disable', 'tools', 'all'), 'enable debug mode'),
    ]

    def __init__(self, host=DEFAULT_HOST, port=DEFAULT_PORT, color=False, timeout=False, debug=False):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.executor = Executor(timeout)
        self._locator = None
        self.configureLog(debug=debug, color=color)

    @staticmethod
    def configureLog(debug='disable', color=True, logNames=None):
        if not logNames:
            logNames = ['cocaine.tools']
        message = '%(message)s'
        level = logging.INFO
        if debug != 'disable':
            message = '[%(asctime)s] %(name)s: %(levelname)-8s: %(message)s'
            level = logging.DEBUG

        ch = logging.StreamHandler()
        if debug == 'disable':
            setattr(logging.StreamHandler, logging.StreamHandler.emit.__name__, interactiveEmit)
        ch.fileno = ch.stream.fileno
        ch.setLevel(level)
        formatter = ColoredFormatter(message, colored=color and sys.stdin.isatty())
        ch.setFormatter(formatter)

        if debug == 'all':
            logNames.append('cocaine')

        for logName in logNames:
            log = logging.getLogger(logName)
            log.setLevel(logging.DEBUG)
            log.propagate = False
            log.addHandler(ch)

    @property
    def locator(self):
        if self._locator:
            return self._locator
        else:
            try:
                locator = Locator()
                locator.connect(self.host, self.port, self.timeout, blocking=True)
                self._locator = locator
                return locator
            except Exception as err:
                raise ToolsError(err)

    def getService(self, name):
        try:
            service = Service(name, blockingConnect=False)
            service.connectThroughLocator(self.locator, self.timeout, blocking=True)
            return service
        except Exception as err:
            raise ToolsError(err)


def middleware(func):
    def extract_dict(source, *keys):
        dest = {}
        for k in keys:
            dest[k] = source.pop(k, None)
        return dest

    def inner(*args, **kwargs):
        opts = extract_dict(kwargs, 'host', 'port', 'color', 'timeout', 'debug')
        if func.__name__ == 'help_inner':
            return func(*args, **kwargs)
        locator = Global(**opts)
        return func(locator, *args, **kwargs)
    return inner


d = Dispatcher(globaloptions=Global.options, middleware=middleware)
appDispatcher = Dispatcher(globaloptions=Global.options, middleware=middleware)
profileDispatcher = Dispatcher(globaloptions=Global.options, middleware=middleware)
runlistDispatcher = Dispatcher(globaloptions=Global.options, middleware=middleware)
crashlogDispatcher = Dispatcher(globaloptions=Global.options, middleware=middleware)
proxyDispatcher = Dispatcher()

@d.command()
def info(options):
    """Show information about cocaine runtime

    Return json-like string with information about cocaine-runtime.
    """
    options.executor.executeAction('info', **{
        'node': options.getService('node'),
        'locator': options.locator
    })


@d.command(usage='SERVICE [METHOD ["ARGS"]]')
def call(options,
         service, method='', args='',
         pretty=('', False, 'make pretty output if output is json')):
    """Invoke specified method from service.

    Performs method invocation from specified service. Service name should be correct string and must be correctly
    located through locator. By default, locator endpoint is `localhost, 10053`, but it can be changed by passing
    global `--host` and `--port` arguments.

    Method arguments should be passed in double quotes as they would be written in Python.
    If no method provided, service API will be printed.
    """
    command = service + '.' + method + '(' + args + ')'
    options.executor.executeAction('call', **{
        'command': command,
        'host': options.host,
        'port': options.port,
        'pretty': pretty
    })


@appDispatcher.command(name='list')
def app_list(options):
    """Show installed applications list."""
    options.executor.executeAction('app:list', **{
        'storage': options.getService('storage')
    })


@appDispatcher.command(usage='--name=NAME', name='view')
def app_view(options,
             name=('n', '', 'application name')):
    """Show manifest context for application.

    If application is not uploaded, an error will be displayed.
    """
    options.executor.executeAction('app:view', **{
        'storage': options.getService('storage'),
        'name': name,
    })


@appDispatcher.command(name='upload', usage='[PATH] [--name=NAME] [--manifest=MANIFEST] [--package=PACKAGE]')
def app_upload(options,
               path=None,
               name=('n', '', 'application name'),
               manifest=('', '', 'manifest file name'),
               package=('', '', 'path to the application archive'),
               venv=('', ('None', 'P', 'R', 'J'), 'virtual environment type (None, P, R, J).')):
    """Upload application with its environment (directory) into the storage.

    Application directory or its subdirectories must contain valid manifest file named `manifest.json` or `manifest`
    otherwise you must specify it explicitly by setting `--manifest` option.

    You can specify application name. By default, leaf directory name is treated as application name.

    If you have already prepared application archive (*.tar.gz), you can explicitly specify path to it by setting
    `--package` option. Note, that PATH and --package options are mutual exclusive as well as --package and --venv
    options.

    If you specify option `--venv`, then virtual environment will be created for application.
    Possible values:
        N - do not create virtual environment (default)
        P - python virtual environment using virtualenv package
        R - ruby virtual environment using Bundler (not yet implemented)
        J - jar archive will be created (not yet implemented)

    You can control process of creating and uploading application by specifying `--debug=tools` option. This is helpful
    when some errors occurred.

    Warning: creating virtual environment may take a long time and can cause timeout. You can increase timeout by
    specifying `--timeout` option.
    """
    if path and package:
        print('Wrong usage: option PATH and --package are mutual exclusive, you can only force one')
        exit(os.EX_USAGE)

    if venv != 'None' and package:
        print('Wrong usage: option --package and --venv are mutual exclusive, you can only force one')
        exit(os.EX_USAGE)

    if package:
        options.executor.executeAction('app:upload-manual', **{
            'storage': options.getService('storage'),
            'name': name,
            'manifest': manifest,
            'package': package
        })
    else:
        if venv != 'None':
            print('You specified building virtual environment')
            print('It may take a long time and can cause timeout. Increase it by specifying `--timeout` option if'
                  ' needed')
        options.executor.executeAction('app:upload', **{
            'storage': options.getService('storage'),
            'path': path,
            'name': name,
            'manifest': manifest,
            'venv': venv
        })


@appDispatcher.command(name='remove')
def app_remove(options,
               name=('n', '', 'application name')):
    """Remove application from storage.

    No error messages will display if specified application is not uploaded.
    """
    options.executor.executeAction('app:remove', **{
        'storage': options.getService('storage'),
        'name': name
    })


@appDispatcher.command(name='start')
def app_start(options,
              name=('n', '', 'application name'),
              profile=('r', '', 'profile name')):
    """Start application with specified profile.

    Does nothing if application is already running.
    """
    options.executor.executeAction('app:start', **{
        'node': options.getService('node'),
        'name': name,
        'profile': profile
    })


@appDispatcher.command(name='pause')
def app_pause(options,
              name=('n', '', 'application name')):
    """Stop application.

    This command is alias for ```cocaine-tool app stop```.
    """
    options.executor.executeAction('app:pause', **{
        'node': options.getService('node'),
        'name': name
    })


@appDispatcher.command(name='stop')
def app_stop(options,
             name=('n', '', 'application name')):
    """Stop application."""
    options.executor.executeAction('app:stop', **{
        'node': options.getService('node'),
        'name': name
    })


@appDispatcher.command(name='restart')
def app_restart(options,
                name=('n', '', 'application name'),
                profile=('r', '', 'profile name')):
    """Restart application.

    Executes ```cocaine-tool app pause``` and ```cocaine-tool app start``` sequentially.

    It can be used to quickly change application profile.
    """
    options.executor.executeAction('app:restart', **{
        'node': options.getService('node'),
        'locator': options.locator,
        'name': name,
        'profile': profile
    })


@appDispatcher.command()
def check(options,
          name=('n', '', 'application name')):
    """Checks application status."""
    options.executor.executeAction('app:check', **{
        'node': options.getService('node'),
        'storage': options.getService('storage'),
        'locator': options.locator,
        'name': name,
    })


@profileDispatcher.command(name='list')
def profile_list(options):
    """Show installed profiles."""
    options.executor.executeAction('profile:list', **{
        'storage': options.getService('storage')
    })


@profileDispatcher.command(name='view')
def profile_view(options,
                 name=('n', '', 'profile name')):
    """Show profile configuration context."""
    options.executor.executeAction('profile:view', **{
        'storage': options.getService('storage'),
        'name': name
    })


@profileDispatcher.command(name='upload')
def profile_upload(options,
                   name=('n', '', 'profile name'),
                   profile=('', '', 'path to profile file')):
    """Upload profile into the storage."""
    options.executor.executeAction('profile:upload', **{
        'storage': options.getService('storage'),
        'name': name,
        'profile': profile
    })


@profileDispatcher.command(name='remove')
def profile_remove(options,
                   name=('n', '', 'profile name')):
    """Remove profile from the storage."""
    options.executor.executeAction('profile:remove', **{
        'storage': options.getService('storage'),
        'name': name
    })


@runlistDispatcher.command(name='list')
def runlist_list(options):
    """Show uploaded runlists."""
    options.executor.executeAction('runlist:list', **{
        'storage': options.getService('storage')
    })


@runlistDispatcher.command(name='view')
def runlist_view(options,
                 name=('n', '', 'name')):
    """Show configuration context for runlist."""
    options.executor.executeAction('runlist:view', **{
        'storage': options.getService('storage'),
        'name': name
    })


@runlistDispatcher.command(name='upload')
def runlist_upload(options,
                   name=('n', '', 'name'),
                   runlist=('', '', 'path to the runlist configuration json file')):
    """Upload runlist with context into the storage."""
    options.executor.executeAction('runlist:upload', **{
        'storage': options.getService('storage'),
        'name': name,
        'runlist': runlist
    })


@runlistDispatcher.command(name='create')
def runlist_create(options,
                   name=('n', '', 'name')):
    """Create runlist and upload it into the storage."""
    options.executor.executeAction('runlist:create', **{
        'storage': options.getService('storage'),
        'name': name
    })


@runlistDispatcher.command(name='remove')
def runlist_remove(options,
                   name=('n', '', 'name')):
    """Remove runlist from the storage."""
    options.executor.executeAction('runlist:remove', **{
        'storage': options.getService('storage'),
        'name': name
    })


@runlistDispatcher.command(name='add-app')
def runlist_add_app(options,
                    name=('n', '', 'runlist name'),
                    app=('', '', 'application name'),
                    profile=('', '', 'suggested profile'),
                    force=('', False, 'create runlist if it is not exist')):
    """Add specified application with profile to the runlist.

    Existence of application or profile is not checked.
    """
    options.executor.executeAction('runlist:add-app', **{
        'storage': options.getService('storage'),
        'name': name,
        'app': app,
        'profile': profile,
        'force': force
    })


@crashlogDispatcher.command(name='list')
def crashlog_list(options,
                  name=('n', '', 'name')):
    """Show crashlogs list for application.

    Prints crashlog list in timestamp - uuid format.
    """
    options.executor.executeAction('crashlog:list', **{
        'storage': options.getService('storage'),
        'name': name
    })


@crashlogDispatcher.command(name='view')
def crashlog_view(options,
                  name=('n', '', 'name'),
                  timestamp=('t', '', 'timestamp')):
    """Show crashlog for application with specified timestamp."""
    options.executor.executeAction('crashlog:view', **{
        'storage': options.getService('storage'),
        'name': name,
        'timestamp': timestamp
    })


@crashlogDispatcher.command(name='remove')
def crashlog_remove(options,
                    name=('n', '', 'name'),
                    timestamp=('t', '', 'timestamp')):
    """Remove crashlog for application with specified timestamp from the storage."""
    options.executor.executeAction('crashlog:remove', **{
        'storage': options.getService('storage'),
        'name': name,
        'timestamp': timestamp
    })


@crashlogDispatcher.command(name='removeall')
def crashlog_removeall(options,
                       name=('n', '', 'name')):
    """Remove all crashlogs for application from the storage."""
    options.executor.executeAction('crashlog:removeall', **{
        'storage': options.getService('storage'),
        'name': name,
    })

DEFAULT_COCAINE_PROXY_PID_FILE = '/var/run/cocaine-python-proxy.pid'


@proxyDispatcher.command()
def start(port=('', 8080, 'server port'),
          count=('', 0, 'server subprocess count (0 means optimal for current CPU count)'),
          config=('', '/etc/cocaine/cocaine-tornado-proxy.conf', 'path to the configuration file'),
          daemon=('', False, 'run as daemon'),
          pidfile=('', DEFAULT_COCAINE_PROXY_PID_FILE, 'pidfile')):
    """Start embedded cocaine proxy.
    """
    Global.configureLog(logNames=['cocaine.tools', 'cocaine.proxy'])
    try:
        proxy.Start(**{
            'port': port,
            'daemon': daemon,
            'count': count,
            'config': config,
            'pidfile': pidfile,
        }).execute()
    except proxy.Error as err:
        logging.getLogger('cocaine.tools').error('Cocaine tool error - %s', err)


@proxyDispatcher.command()
def stop(pidfile=('', DEFAULT_COCAINE_PROXY_PID_FILE, 'pidfile')):
    """Stop embedded cocaine proxy.
    """
    Global.configureLog(logNames=['cocaine.tools', 'cocaine.proxy'])
    try:
        proxy.Stop(**{
            'pidfile': pidfile,
        }).execute()
    except proxy.Error as err:
        logging.getLogger('cocaine.tools').error('Cocaine tool error - %s', err)


@proxyDispatcher.command()
def status(pidfile=('', DEFAULT_COCAINE_PROXY_PID_FILE, 'pidfile')):
    """Show embedded cocaine proxy status.
    """
    Global.configureLog(logNames=['cocaine.tools', 'cocaine.proxy'])
    try:
        proxy.Status(**{
            'pidfile': pidfile,
        }).execute()
    except proxy.Error as err:
        logging.getLogger('cocaine.tools').error('Cocaine tool error - %s', err)


d.nest('app', appDispatcher, 'application commands')
d.nest('profile', profileDispatcher, 'profile commands')
d.nest('runlist', runlistDispatcher, 'runlist commands')
d.nest('crashlog', crashlogDispatcher, 'crashlog commands')
d.nest('proxy', proxyDispatcher, 'cocaine proxy commands')