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
        from cocaine.futures.chain import ChainFactory
        from cocaine.services import Service
        import os

        locateItems = {
            'app': ['manifests', ('app', )],
            'profile': ['profiles', ('runlist',)],
            'runlist': ['runlists', ('profile',)],
        }

        config = {
            'locateItem': getOption('--locator_type', 'app'),
            'host': getOption('--host', 'localhost'),
            'port': getOption('--port', '10053')
        }

        def locateApps():
            return storage.find(*locateItems.get(config['locateItem']))

        def printResult(apps):
            print(' '.join(apps.get()))
            loop.stop()

        storage = Service('storage', config['host'], int(config['port']))
        ChainFactory().then(locateApps).then(printResult).run()
        loop = IOLoop.instance()
        loop.add_timeout(time() + 0.25, lambda: loop.stop())
        loop.start()
    except Exception as err:
        # Hidden log feature :)
        with open(os.devnull, 'w') as fh:
            fh.write(err.message)
