from tornado.ioloop import IOLoop
from cocaine.services import Service
from cocaine.tools.tools import AppUploadFromRepositoryAction
import logging


__author__ = 'EvgenySafronov <division494@gmail.com>'


storage = Service('storage')


if __name__ == '__main__':
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(name)s: %(levelname)-8s: %(message)s')
    ch.setFormatter(formatter)

    logNames = [
        __name__,
        'cocaine.tools.installer',
        'cocaine.futures.chain',
        'cocaine.testing.mocks',
    ]

    for logName in logNames:
        log = logging.getLogger(logName)
        log.setLevel(logging.DEBUG)
        log.propagate = False
        log.addHandler(ch)


    a1 = AppUploadFromRepositoryAction(storage, **{'url': 'file:///Users/esafronov/mock_repo/repo_echo'})
    a2 = AppUploadFromRepositoryAction(storage, **{'url': 'file:///Users/esafronov/mock_repo/repo_echo'})
    a3 = AppUploadFromRepositoryAction(storage, **{'url': 'file:///Users/esafronov/mock_repo/repo_echoWRONG'})
    a4 = AppUploadFromRepositoryAction(storage, **{'url': 'file:///Users/esafronov/mock_repo/repo_echo'})
    a5 = AppUploadFromRepositoryAction(storage, **{'url': 'file:///Users/esafronov/mock_repo/repo_echo'})
    # Run all of them simultaneously
    r = a1.execute()
    r = a2.execute()
    r = a3.execute()
    r = a4.execute()
    r = a5.execute()
    IOLoop.instance().start()
    # print('R', r)