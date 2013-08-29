Cocaine Tools Command Line Interface
====================================
This part describes cocaine command line tools.
It is useful for management your cocaine cloud, uploading applications, profiles and other stuff.


Common tools
------------------------------------
This part describes common tools.


cocaine-tool info
''''''''''''''''''''''''''''''''''''
Show information about cocaine runtime

    Return json-like string with information about cocaine-runtime.

    >>> cocaine-tool info
    {
        "uptime": 738,
        "identity": "dhcp-666-66-wifi.yandex.net"
    }

    If some applications is running, its information will be displayed too.

    >>> cocaine-tool info
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


cocaine-tool call
''''''''''''''''''''''''''''''''''''
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


Application specific tools
------------------------------------
This part describes application specific tools.

cocaine-tool app list
''''''''''''''''''''''''''''''''''''
Show installed applications list.

    Returns list of installed applications.

    >>> cocaine-tools app list
    [
        "app1",
        "app2"
    ]

cocaine-tool app view
''''''''''''''''''''''''''''''''''''
Show manifest context for application.

    If application is not uploaded, an error will be displayed.

    :name: application name.

    >>> cocaine-tool app view --name Echo
    {
        "slave": "/home/satan/echo/echo.py"
    }

cocaine-tool app upload
''''''''''''''''''''''''''''''''''''
Upload application with its environment (directory) into the storage.

    Application directory or its subdirectories must contain valid manifest file named `manifest.json` or `manifest`
    otherwise you must specify it explicitly by setting `--manifest` option.

    You can specify application name. By default, leaf directory name is treated as application name.

    If you have already prepared application archive (\*.tar.gz), you can explicitly specify path to it by setting
    `--package` option. Note, that PATH and --package options are mutual exclusive as well as --package and --venv
    options.

    If you specify option `--venv`, then virtual environment will be created for application.

    Possible values:
        * N - do not create virtual environment (default)
        * P - python virtual environment using virtualenv package
        * R - ruby virtual environment using Bundler (not yet implemented)
        * J - jar archive will be created (not yet implemented)

    Algorithm of creating and configuring **python virtual environment** contains following steps:
        * locating `virtualenv` module. It must be installed.
        * creating clear virtual environment via `virtualenv` module.
        * locating `manifest.json` or `manifest` file somewhere in the target directory or its subdirectories.
        * creating `bootstrap.sh` scrips for correct starting application via virtual environment.
        * cloning and installing cocaine-framework-python through git.
        * locating `requirements.txt` or `requirements` file somewhere in the target directory or its subdirectories.
        * installing all requirements specified in the file above (if it has been found)

    You can control process of creating and uploading application by specifying `--debug=tools` option. This is helpful
    when some errors occurred.

    .. warning:: Creating virtual environment may take a long time and can cause timeout. You can increase timeout by
                 specifying `--timeout` option.

    .. warning:: This is experimental feature.

    :path: path to the application root.
    :name: application name. If it is not specified, application will be named as its directory name.
    :manifest: path to application manifest json file.
    :package: path to application archive.
    :venv: virtual environment type. This is optional parameter and does nothing if not specified. Otherwise virtual
           environment will be created and configured.

    *The simplest usage*

    >>> cd /home/user/your_app
    >>> cocaine-tool app upload
    Application your_app has been successfully uploaded

    *But you can specify path directly as first positional argument like this*

    >>> cocaine-tool app upload ~/echo
    Application echo has been successfully uploaded

    *Explicitly set application name*

    >>> cocaine-tool app upload ~/echo --name TheEchoApp
    Application TheEchoApp has been successfully uploaded

    *If you want to explicitly specify application archive*

    >>> cocaine-tool app upload --name echo --manifest ~/echo/manifest.json --package ~/echo/echo.tar.gz
    Application echo has been successfully uploaded

    *Let's create python virtual environment and see detail log*

    >>> cocaine-tool app upload ~/echo --venv P --timeout 60 --debug tools
    You specified building virtual environment
    It may take a long time and can cause timeout. Increase it by specifying `--timeout` option if needed
    cocaine.tools.installer: DEBUG   : Filenames found: [('../examples/echo/manifest.json', 111)]
    cocaine.tools: DEBUG   : Repository temporary path - "/var/folders/dx/sww3lm4j7x73x7x3njzv770jqq7lhf/T/tmpSO_cva/repo"
    cocaine.tools: DEBUG   : Creating virtual environment "P" ...
    cocaine.tools.installer: DEBUG   : Start installing python module
    ...
    cocaine.tools.installer: DEBUG   : All requirements has been successfully installed
    cocaine.tools.installer: DEBUG   : Python module has been successfully installed
    cocaine.tools: DEBUG   : Creating package
    Application echo has been successfully uploaded

cocaine-tool app remove
''''''''''''''''''''''''''''''''''''
Remove application from storage.

    No error messages will display if specified application is not uploaded.

    :name: application name.

    >>> cocaine-tool app remove --name echo
    The app "echo" has been successfully removed

cocaine-tool app start
''''''''''''''''''''''''''''''''''''
Start application with specified profile.

    Does nothing if application is already running.

    :name: application name.
    :profile: desired profile.

    >>> cocaine-tool app start --name Echo --profile EchoDefault
    {
        "Echo": "the app has been started"
    }

    *If application is already running*

    >>> cocaine-tool app start --name Echo --profile EchoDefault
    {
        "Echo": "the app is already running"
    }

cocaine-tool app pause/stop
''''''''''''''''''''''''''''''''''''
Stop application.

    This command is alias for ```cocaine-tool app stop```.

    :name: application name.

    >>> cocaine-tool app pause --name Echo
    {
        "Echo": "the app has been stopped"
    }

    *For non running application*

    >>> cocaine-tool app pause --name Echo
    {
        "Echo": "the app is not running"
    }

cocaine-tool app restart
''''''''''''''''''''''''''''''''''''
Restart application.

    Executes ```cocaine-tool app pause``` and ```cocaine-tool app start``` sequentially.

    It can be used to quickly change application profile.

    :name: application name.
    :profile: desired profile. If no profile specified, application will be restarted with the current profile.

    *Usual case*

    >>> cocaine-tool app restart --name Echo
    [
        {
            "Echo": "the app has been stopped"
        },
        {
            "Echo": "the app has been started"
        }
    ]

    *If application was not run and no profile name provided*

    >>> cocaine-tool app restart --name Echo
    Error occurred: Application "Echo" is not running and profile not specified

    *But if we specify profile name*

    >>> cocaine-tool app restart --name Echo --profile EchoProfile
    [
        {
            "Echo": "the app is not running"
        },
        {
            "Echo": "the app has been started"
        }
    ]

    *In case wrong profile just stops application*

    >>> cocaine-tool app restart --name Echo --profile EchoProf
    [
        {
            "Echo": "the app has been stopped"
        },
        {
            "Echo": "object 'EchoProf' has not been found in 'profiles'"
        }
    ]

cocaine-tool app check
''''''''''''''''''''''''''''''''''''
Checks application status.

    :name: application name.

    >>> cocaine-tool app check --name Echo
    {
        "Echo": "stopped or missing"
    }


Profile specific tools
------------------------------------
This part describes profile specific tools.

cocaine-tool profile list
''''''''''''''''''''''''''''''''''''
Show installed profiles.

    Returns list of installed profiles.

    >>> cocaine-tool profile list
    [
        "EchoProfile"
    ]

cocaine-tool profile view
''''''''''''''''''''''''''''''''''''
Show profile configuration context.

    :name: profile name

    >>> cocaine-tool profile view --name EchoProfile
    {
        "pool-limit": 4
    }

cocaine-tool profile upload
''''''''''''''''''''''''''''''''''''
Upload profile into the storage.

    :name: profile name.
    :profile: path to the profile json file.

    >>> cocaine-tool profile upload --name EchoProfile --profile ../examples/echo/profile.json
    The profile "EchoProfile" has been successfully uploaded

cocaine-tool profile remove
''''''''''''''''''''''''''''''''''''
Remove profile from the storage.

    :name: profile name.

    >>> cocaine-tool profile remove --name EchoProfile
    The profile "EchoProfile" has been successfully removed


Profile specific tools
------------------------------------
This part describes runlist specific tools.

cocaine-tool runlist list
''''''''''''''''''''''''''''''''''''
Show uploaded runlists.

    Returns list of installed runlists.

    >>> cocaine-tool runlist list
    [
        "default"
    ]

cocaine-tool runlist view
''''''''''''''''''''''''''''''''''''
Show configuration context for runlist.

    :name: runlist name.

    >>> cocaine-tool runlist view --name default
    {
        "Echo": "EchoProfile"
    }

cocaine-tool runlist upload
''''''''''''''''''''''''''''''''''''
Upload runlist with context into the storage.

    :name: runlist name.
    :runlist: path to the runlist configuration json file.

    >>> cocaine-tool runlist upload --name default --runlist ../examples/echo/runlsit.json
    The runlist "default" has been successfully uploaded

cocaine-tool runlist create
''''''''''''''''''''''''''''''''''''
Create runlist and upload it into the storage.

    :name: runlist name.

    >>> cocaine-tool runlist create --name default
    The runlist "default" has been successfully created

cocaine-tool runlist remove
''''''''''''''''''''''''''''''''''''
Remove runlist from the storage.

    :name: runlist name.

    >>> cocaine-tool runlist remove --name default
    The runlist "default" has been successfully removed

cocaine-tool runlist add-app
''''''''''''''''''''''''''''''''''''
Add specified application with profile to the runlist.

    Existence of application or profile is not checked.

    :name: runlist name.
    :app: application name.
    :profile: suggested profile name.

    >>> cocaine-tool runlist add-app --name default --app Echo --profile EchoProfile
    {
        "status": "Success",
        "added": {
            "profile": "EchoProfile",
            "app": "Echo"
        },
        "runlist": "default"
    }


Crashlog specific tools
------------------------------------
This part describes crashlog specific tools.

cocaine-tool crashlog list
''''''''''''''''''''''''''''''''''''
Show crashlogs list for application.

    Prints crashlog list in timestamp - uuid format.

    :name: application name.

    >>> cocaine-tool crashlog list --name Echo
    Currently available crashlogs for application 'Echo'
    1372165800114964 Tue Jun 25 17:10:00 2013 2d92aa19-535d-4aa3-9c68-7aa32f9967df
    1372166090866950 Tue Jun 25 17:14:50 2013 e27b2ccc-64a6-4958-a9b4-f2abac974e4a
    1372166371522675 Tue Jun 25 17:19:31 2013 762f2fb8-8d8c-4b1d-ab79-14cdb6332ecb
    1372166822795587 Tue Jun 25 17:27:02 2013 1fd3ca03-3402-4279-8b2b-1e40ff92f4a7

cocaine-tool crashlog view
''''''''''''''''''''''''''''''''''''
Show crashlog for application with specified timestamp.

    :name: application name.
    :timestamp: desired timestamp - time_t format.

    >>> cocaine-tool crashlog view --name Echo --timestamp 1372165800114964
    Crashlog:
      File "/Library/Python/2.7/site-packages/tornado-3.1-py2.7.egg/tornado/ioloop.py", line 672, in start
        self._handlers[fd](fd, events)
      File "/Library/Python/2.7/site-packages/tornado-3.1-py2.7.egg/tornado/stack_context.py", line 331, in wrapped
        raise_exc_info(exc)
      File "/Library/Python/2.7/site-packages/tornado-3.1-py2.7.egg/tornado/stack_context.py", line 302, in wrapped
        ret = fn(*args, **kwargs)
      File "build/bdist.macosx-10.8-intel/egg/cocaine/asio/ev.py", line 93, in proxy
        self._callbacks[(fd, self.WRITE)]()
      File "build/bdist.macosx-10.8-intel/egg/cocaine/asio/stream.py", line 128, in _on_event
        sent = self.pipe.write(buffer(current, self.tx_offset))
    TypeError: an integer is required
    ERROR:tornado.application:Exception in I/O handler for fd 11

cocaine-tool crashlog remove
''''''''''''''''''''''''''''''''''''
Remove crashlog for application with specified timestamp from the storage.

    :name: application name.
    :timestamp: desired timestamp - time_t format.

    >>> cocaine-tool crashlog remove --name Echo --timestamp 1372165800114964
    Crashlog for app "Echo" has been removed

cocaine-tool crashlog removeall
''''''''''''''''''''''''''''''''''''
Remove all crashlogs for application from the storage.

    :name: application name.

    >>> cocaine-tool crashlog removeall --name Echo
    Crashlogs for app "Echo" have been removed