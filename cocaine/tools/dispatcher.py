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
    """
    Show information about cocaine runtime

    Return json-like string with information about cocaine-runtime.

    >>> cocaine-tools info
    {
        "uptime": 738,
        "identity": "dhcp-666-66-wifi.yandex.net"
    }

    If some applications is running, its information will be displayed too.

    >>> cocaine-tools info
    {
        "uptime": 738,
        "apps": {
            "Echo": {
                "load-median": 0,
                "profile": "EchoProfile",
                "sessions": {
                    "pending": 0
                },
                "queue": {
                    "depth": 0,
                    "capacity": 100
                },
                "state": "running",
                "slaves": {
                    "active": 0,
                    "idle": 0,
                    "capacity": 4
                }
            }
        },
        "identity": "dhcp-666-66-wifi.yandex.net"
    }
    """
    locator.nodeExecutor.executeAction('info', **{})

@d.command()
def call(locator,
         service, method='', args=''):
    """
    Invoke specified method from service.

    Performs method invocation from specified service. Service name should be correct string and must be correctly
    located through locator. By default, locator endpoint is ```localhost, 10053```, but it can be changed by passing
    global `--host` and `--port` arguments.

    Method arguments should be passed in double quotes as they would be written in Python.
    If no method provided, service API will be printed.

    *Request service API*:

    >>> cocaine-tool call node
    API of service "node": [
        "start_app",
        "pause_app",
        "info"
    ]

    *Invoke `info` method from service `node`*:

    >>> cocaine-tool call node info
    {'uptime': 1855, 'identity': 'dhcp-666-66-wifi.yandex.net'}

    *Specifying locator endpoint*

    >>> cocaine-tool call node info --host localhost --port 10052
    LocatorResolveError: Unable to resolve API for service node at localhost:10052, because [Errno 61] Connection
    refused

    *Passing complex method arguments*

    >>> cocaine-tool call storage read "'apps', 'Echo'"
    [Lot of binary data]
    """
    command = service + '.' + method + '(' + args + ')'
    locator.nodeExecutor.executeAction('call', **{
        'command': command,
    })

@appDispatcher.command(name='list')
def app_list(locator):
    """
    Show installed applications list

    >>> cocaine-tools app list
    [
        "app1",
        "app2"
    ]
    """
    locator.storageExecutor.executeAction('app:list', **{})


@appDispatcher.command(usage='--name=NAME', name='view')
def app_view(locator,
             name=('n', '', 'application name')):
    """
    Show manifest context for application
    """
    locator.storageExecutor.executeAction('app:view', **{
        'name': name,
    })


@appDispatcher.command(name='upload')
def app_upload(locator,
               name=('n', '', 'application name'),
               manifest=('', '', 'manifest file name'),
               package=('', '', 'location of the app source package')):
    """
    Uploads application into storage
    """
    locator.storageExecutor.executeAction('app:upload', **{
        'name': name,
        'manifest': manifest,
        'package': package
    })


@appDispatcher.command(name='upload2')
def app_upload2(locator,
                path,
                name=None):
    """
    Uploads application with its environment (directory) into storage.

    Application directory must contain valid manifest file.
    You can specify application name. By default, directory name is treated as application name.
    """
    locator.storageExecutor.executeAction('app:upload2', **{
        'path': path,
        'name': name
    })


@appDispatcher.command(name='remove')
def app_remove(locator,
               name=('n', '', 'application name')):
    """
    Removes application from storage
    """
    locator.storageExecutor.executeAction('app:remove', **{
        'name': name
    })


@appDispatcher.command(name='start')
def app_start(locator,
              name=('n', '', 'application name'),
              profile=('r', '', 'profile name')):
    """
    Starts application
    """
    locator.nodeExecutor.executeAction('app:start', **{
        'name': name,
        'profile': profile
    })


@appDispatcher.command(name='pause')
def app_pause(locator,
              name=('n', '', 'application name')):
    """
    Pauses application

    This command is alias for `cocaine-tool app stop`
    """
    locator.nodeExecutor.executeAction('app:pause', **{
        'name': name
    })


@appDispatcher.command(name='stop')
def app_stop(locator,
             name=('n', '', 'application name')):
    """
    Stops application
    """
    locator.nodeExecutor.executeAction('app:stop', **{
        'name': name
    })


@appDispatcher.command(name='restart')
def app_restart(locator,
                name=('n', '', 'application name'),
                profile=('r', '', 'profile name')):
    """
    Restarts application

    Equivalent of `cocaine-tool app pause --name [NAME]; cocaine-tool app start --name [NAME] --profile [PROFILE]`.
    If profile is not specified, application will be restarted with the current profile.
    """
    locator.nodeExecutor.executeAction('app:restart', **{
        'name': name,
        'profile': profile
    })


@appDispatcher.command()
def check(locator,
          name=('n', '', 'application name')):
    """
    Checks application status
    """
    locator.nodeExecutor.executeAction('app:check', **{
        'name': name
    })


@profileDispatcher.command(name='list')
def profile_list(locator):
    """
    Shows installed profiles list
    """
    locator.storageExecutor.executeAction('profile:list', **{})


@profileDispatcher.command(name='view')
def profile_view(locator,
                 name=('n', '', 'profile name')):
    """
    Shows configuration context
    """
    locator.storageExecutor.executeAction('profile:view', **{
        'name': name
    })


@profileDispatcher.command(name='upload')
def profile_upload(locator,
                   name=('n', '', 'profile name'),
                   profile=('', '', 'path to profile file')):
    """
    Uploads profile into storage
    """
    locator.storageExecutor.executeAction('profile:upload', **{
        'name': name,
        'manifest': profile
    })


@profileDispatcher.command(name='remove')
def profile_upload(locator,
                   name=('n', '', 'profile name')):
    """
    Removes profile from storage
    """
    locator.storageExecutor.executeAction('profile:remove', **{
        'name': name
    })


@runlistDispatcher.command(name='list')
def runlist_list(locator):
    """
    Shows uploaded runlists
    """
    locator.storageExecutor.executeAction('runlist:list', **{})


@runlistDispatcher.command(name='view')
def runlist_view(locator,
                 name=('n', '', 'name')):
    """
    Shows configuration context for runlist
    """
    locator.storageExecutor.executeAction('runlist:view', **{
        'name': name
    })


@runlistDispatcher.command(name='upload')
def runlist_upload(locator,
                   name=('n', '', 'name'),
                   runlist=('', '', 'runlist')):
    """
    Uploads runlist with context into storage
    """
    locator.storageExecutor.executeAction('runlist:upload', **{
        'name': name,
        'manifest': runlist
    })


@runlistDispatcher.command(name='remove')
def runlist_remove(locator,
                   name=('n', '', 'name')):
    """
    Removes runlist from storage
    """
    locator.storageExecutor.executeAction('runlist:remove', **{
        'name': name
    })


@runlistDispatcher.command(name='add-app')
def runlist_add_app(locator,
                    name=('n', '', 'runlist name'),
                    app=('', '', 'application name'),
                    profile=('', '', 'suggested profile')):
    """
    Adds specified application with profile to runlist
    """
    locator.storageExecutor.executeAction('runlist:add-app', **{
        'name': name,
        'app': app,
        'profile': profile
    })


@crashlogDispatcher.command(name='list')
def crashlog_list(locator,
                  name=('n', '', 'name')):
    """
    Shows crashlogs list for application
    """
    locator.storageExecutor.executeAction('crashlog:list', **{
        'name': name
    })


@crashlogDispatcher.command(name='view')
def crashlog_view(locator,
                  name=('n', '', 'name'),
                  timestamp=('t', '', 'timestamp')):
    """
    Shows crashlog for application with specified timestamp
    """
    locator.storageExecutor.executeAction('crashlog:view', **{
        'name': name,
        'manifest': timestamp
    })


@crashlogDispatcher.command(name='remove')
def crashlog_remove(locator,
                    name=('n', '', 'name'),
                    timestamp=('t', '', 'timestamp')):
    """
    Removes crashlog for application with specified timestamp
    """
    locator.storageExecutor.executeAction('crashlog:remove', **{
        'name': name,
        'manifest': timestamp
    })


@crashlogDispatcher.command(name='removeall')
def crashlog_removeall(locator,
                       name=('n', '', 'name')):
    """
    Removes all crashlogs for application
    """
    locator.storageExecutor.executeAction('crashlog:removeall', **{
        'name': name,
        'manifest': None
    })


d.nest('app', appDispatcher, 'application commands')
d.nest('profile', profileDispatcher, 'profile commands')
d.nest('runlist', runlistDispatcher, 'runlist commands')
d.nest('crashlog', crashlogDispatcher, 'crashlog commands')