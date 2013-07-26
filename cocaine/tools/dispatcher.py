import logging
from opster import Dispatcher
from cocaine.tools.cli import NodeExecutor, StorageExecutor, coloredOutput

__author__ = 'Evgeny Safronov <division494@gmail.com>'


DESCRIPTION = ''
DEFAULT_HOST = 'localhost'
DEFAULT_PORT = 10053


class Locator(object):
    options = [
        ('h', 'host', DEFAULT_HOST, 'hostname'),
        ('p', 'port', DEFAULT_PORT, 'port'),
        ('', 'color', False, 'enable colored output'),
        ('', 'timeout', 1.0, 'timeout, s'),
        ('', 'debug', ('disable', 'tools', 'all'), 'enable debug mode')
    ]

    def __init__(self, host=DEFAULT_HOST, port=DEFAULT_PORT, color=False, timeout=False, debug=False):
        config = {
            'host': host,
            'port': port,
            'timeout': timeout,
            'debug': debug
        }
        self.nodeExecutor = NodeExecutor(**config)
        self.storageExecutor = StorageExecutor(**config)
        if not color:
            coloredOutput.disable()

        debugLevel = config['debug']
        if debugLevel != 'disable':
            ch = logging.StreamHandler()
            ch.fileno = ch.stream.fileno
            ch.setLevel(logging.DEBUG)
            formatter = logging.Formatter('%(name)s: %(levelname)-8s: %(message)s')
            ch.setFormatter(formatter)

            logNames = [
                __name__,
                'cocaine.tools'
            ]
            if debugLevel == 'all':
                logNames.append('cocaine.futures.chain')
                logNames.append('cocaine.testing.mocks')

            for logName in logNames:
                log = logging.getLogger(logName)
                log.setLevel(logging.DEBUG)
                log.propagate = False
                log.addHandler(ch)


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
        locator = Locator(**opts)
        return func(locator, *args, **kwargs)
    return inner


d = Dispatcher(globaloptions=Locator.options, middleware=middleware)
appDispatcher = Dispatcher(globaloptions=Locator.options, middleware=middleware)
profileDispatcher = Dispatcher(globaloptions=Locator.options, middleware=middleware)
runlistDispatcher = Dispatcher(globaloptions=Locator.options, middleware=middleware)
crashlogDispatcher = Dispatcher(globaloptions=Locator.options, middleware=middleware)


@d.command()
def info(locator):
    """Show information about cocaine runtime

    Return json-like string with information about cocaine-runtime.
    """
    locator.nodeExecutor.executeAction('info', **{})


@d.command()
def call(locator,
         service, method='', args=''):
    """Invoke specified method from service.

    Performs method invocation from specified service. Service name should be correct string and must be correctly
    located through locator. By default, locator endpoint is ```localhost, 10053```, but it can be changed by passing
    global `--host` and `--port` arguments.

    Method arguments should be passed in double quotes as they would be written in Python.
    If no method provided, service API will be printed.
    """
    command = service + '.' + method + '(' + args + ')'
    locator.nodeExecutor.executeAction('call', **{
        'command': command,
    })

@appDispatcher.command(name='list')
def app_list(locator):
    """Show installed applications list."""
    locator.storageExecutor.executeAction('app:list', **{})


@appDispatcher.command(usage='--name=NAME', name='view')
def app_view(locator,
             name=('n', '', 'application name')):
    """Show manifest context for application.

    If application is not uploaded, an error will be displayed.
    """
    locator.storageExecutor.executeAction('app:view', **{
        'name': name,
    })


@appDispatcher.command(usage='--name=NAME --manifest=MANIFEST --package=PACKAGE', name='upload')
def app_upload(locator,
               name=('n', '', 'application name'),
               manifest=('', '', 'manifest file name'),
               package=('', '', 'location of the app source package')):
    """Upload application into the storage"""
    locator.storageExecutor.executeAction('app:upload', **{
        'name': name,
        'manifest': manifest,
        'package': package
    })


@appDispatcher.command(name='upload2', usage='PATH [NAME] [--venv=VIRTUAL_ENVIRONMENT]')
def app_upload2(locator,
                path,
                name=None,
                venv=('', ('N', 'P', 'R', 'J'), 'virtual environment type')):
    """Upload application with its environment (directory) into the storage.

    Application directory must contain valid manifest file.
    You can specify application name. By default, directory name is treated as application name.
    """
    locator.storageExecutor.executeAction('app:upload2', **{
        'path': path,
        'name': name,
        'venv': venv
    })


@appDispatcher.command(name='remove')
def app_remove(locator,
               name=('n', '', 'application name')):
    """Remove application from storage.

    No error messages will display if specified application is not uploaded.
    """
    locator.storageExecutor.executeAction('app:remove', **{
        'name': name
    })


@appDispatcher.command(name='start')
def app_start(locator,
              name=('n', '', 'application name'),
              profile=('r', '', 'profile name')):
    """Start application with specified profile.

    Does nothing if application is already running.
    """
    locator.nodeExecutor.executeAction('app:start', **{
        'name': name,
        'profile': profile
    })


@appDispatcher.command(name='pause')
def app_pause(locator,
              name=('n', '', 'application name')):
    """Stop application.

    This command is alias for ```cocaine-tool app stop```.
    """
    locator.nodeExecutor.executeAction('app:pause', **{
        'name': name
    })


@appDispatcher.command(name='stop')
def app_stop(locator,
             name=('n', '', 'application name')):
    """Stop application."""
    locator.nodeExecutor.executeAction('app:stop', **{
        'name': name
    })


@appDispatcher.command(name='restart')
def app_restart(locator,
                name=('n', '', 'application name'),
                profile=('r', '', 'profile name')):
    """Restart application.

    Executes ```cocaine-tool app pause``` and ```cocaine-tool app start``` sequentially.

    It can be used to quickly change application profile.
    """
    locator.nodeExecutor.executeAction('app:restart', **{
        'name': name,
        'profile': profile
    })


@appDispatcher.command()
def check(locator,
          name=('n', '', 'application name')):
    """Checks application status."""
    locator.nodeExecutor.executeAction('app:check', **{
        'name': name
    })


@profileDispatcher.command(name='list')
def profile_list(locator):
    """Show installed profiles."""
    locator.storageExecutor.executeAction('profile:list', **{})


@profileDispatcher.command(name='view')
def profile_view(locator,
                 name=('n', '', 'profile name')):
    """Show profile configuration context."""
    locator.storageExecutor.executeAction('profile:view', **{
        'name': name
    })


@profileDispatcher.command(name='upload')
def profile_upload(locator,
                   name=('n', '', 'profile name'),
                   profile=('', '', 'path to profile file')):
    """Upload profile into the storage."""
    locator.storageExecutor.executeAction('profile:upload', **{
        'name': name,
        'manifest': profile
    })


@profileDispatcher.command(name='remove')
def profile_remove(locator,
                   name=('n', '', 'profile name')):
    """Remove profile from the storage."""
    locator.storageExecutor.executeAction('profile:remove', **{
        'name': name
    })


@runlistDispatcher.command(name='list')
def runlist_list(locator):
    """Show uploaded runlists."""
    locator.storageExecutor.executeAction('runlist:list', **{})


@runlistDispatcher.command(name='view')
def runlist_view(locator,
                 name=('n', '', 'name')):
    """Show configuration context for runlist."""
    locator.storageExecutor.executeAction('runlist:view', **{
        'name': name
    })


@runlistDispatcher.command(name='upload')
def runlist_upload(locator,
                   name=('n', '', 'name'),
                   runlist=('', '', 'path to the runlist configuration json file')):
    """Upload runlist with context into the storage."""
    locator.storageExecutor.executeAction('runlist:upload', **{
        'name': name,
        'manifest': runlist
    })


@runlistDispatcher.command(name='create')
def runlist_create(locator,
                   name=('n', '', 'name')):
    """Create runlist and upload it into the storage."""
    locator.storageExecutor.executeAction('runlist:create', **{
        'name': name
    })


@runlistDispatcher.command(name='remove')
def runlist_remove(locator,
                   name=('n', '', 'name')):
    """Remove runlist from the storage."""
    locator.storageExecutor.executeAction('runlist:remove', **{
        'name': name
    })


@runlistDispatcher.command(name='add-app')
def runlist_add_app(locator,
                    name=('n', '', 'runlist name'),
                    app=('', '', 'application name'),
                    profile=('', '', 'suggested profile')):
    """Add specified application with profile to the runlist.

    Existence of application or profile is not checked.
    """
    locator.storageExecutor.executeAction('runlist:add-app', **{
        'name': name,
        'app': app,
        'profile': profile
    })


@crashlogDispatcher.command(name='list')
def crashlog_list(locator,
                  name=('n', '', 'name')):
    """Show crashlogs list for application.

    Prints crashlog list in timestamp - uuid format.
    """
    locator.storageExecutor.executeAction('crashlog:list', **{
        'name': name
    })


@crashlogDispatcher.command(name='view')
def crashlog_view(locator,
                  name=('n', '', 'name'),
                  timestamp=('t', '', 'timestamp')):
    """Show crashlog for application with specified timestamp."""
    locator.storageExecutor.executeAction('crashlog:view', **{
        'name': name,
        'manifest': timestamp
    })


@crashlogDispatcher.command(name='remove')
def crashlog_remove(locator,
                    name=('n', '', 'name'),
                    timestamp=('t', '', 'timestamp')):
    """Remove crashlog for application with specified timestamp from the storage."""
    locator.storageExecutor.executeAction('crashlog:remove', **{
        'name': name,
        'manifest': timestamp
    })


@crashlogDispatcher.command(name='removeall')
def crashlog_removeall(locator,
                       name=('n', '', 'name')):
    """Remove all crashlogs for application from the storage."""
    locator.storageExecutor.executeAction('crashlog:removeall', **{
        'name': name,
        'manifest': None
    })


d.nest('app', appDispatcher, 'application commands')
d.nest('profile', profileDispatcher, 'profile commands')
d.nest('runlist', runlistDispatcher, 'runlist commands')
d.nest('crashlog', crashlogDispatcher, 'crashlog commands')