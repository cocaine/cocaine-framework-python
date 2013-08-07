#!/usr/bin/env python

__author__ = 'EvgenySafronov <division494@gmail.com>'


def getOption(name, default):
    value = default
    if name in sys.argv:
        index = sys.argv.index(name)
        if index < len(sys.argv) - 1:
            value = sys.argv[index + 1]
            if value == '=' and index + 1 < len(sys.argv) - 2:
                value = sys.argv[index + 2]
    elif name + '=' in sys.argv:
        index = sys.argv.index(name + '=')
        if index < len(sys.argv) - 1:
            value = sys.argv[index + 1]
    return value


if __name__ == '__main__':
    try:
        import sys
        from time import time
        from tornado.ioloop import IOLoop
        from cocaine.futures.chain import Chain
        from cocaine.services import Service
        import os

        ADEQUATE_TIMEOUT = 0.25

        locateItems = {
            'app': ['manifests', ('app', )],
            'profile': ['profiles', ('profile',)],
            'runlist': ['runlists', ('runlist',)],
        }

        config = {
            'locateItem': getOption('--locator_type', 'app'),
            'host': getOption('--host', 'localhost'),
            'port': getOption('--port', '10053')
        }

        def locateApps():
            apps = yield storage.find(*locateItems.get(config['locateItem']))
            with open('/tmp/1.txt', 'w') as fh:
                fh.write(' '.join(apps))
            if apps:
                print(' '.join(apps))
                loop.stop()

        storage = Service('storage', config['host'], int(config['port']))
        Chain().then(locateApps).run()
        loop = IOLoop.instance()
        loop.add_timeout(time() + ADEQUATE_TIMEOUT, lambda: loop.stop())
        loop.start()
    except Exception as err:
        # Hidden log feature :)
        with open(os.devnull, 'w') as fh:
            fh.write(str(err))
