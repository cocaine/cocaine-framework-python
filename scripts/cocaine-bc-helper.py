#!/usr/bin/python
__author__ = 'EvgenySafronov <division494@gmail.com>'


def getOption(optionName, default):
    for name in [optionName, optionName + '=']:
        if name in sys.argv:
            index = sys.argv.index(name)
            return sys.argv[index + 1] if index + 1 < len(sys.argv) else default
        for arg in sys.argv:
            if arg.startswith(name):
                return arg[len(name) + 1:] or default
    return default


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
            'port': getOption('--port', 10053)
        }

        def locateApps():
            return storage.find(*locateItems.get(config['locateItem']))

        def printResult(apps):
            print(' '.join(apps.get()))
            loop.stop()

        storage = Service('storage', config['host'], config['port'])
        ChainFactory().then(locateApps).then(printResult).run()
        loop = IOLoop.instance()
        loop.add_timeout(time() + 0.5, lambda: loop.stop())
        loop.start()
    except Exception as err:
        # Hidden log feature :)
        with open(os.devnull, 'w') as fh:
            fh.write(err.message)
