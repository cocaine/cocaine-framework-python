from tornado.ioloop import IOLoop
from cocaine.services import Service
from cocaine.tools.tools import AppUploadFromRepositoryAction
import logging


__author__ = 'EvgenySafronov <division494@gmail.com>'


storage = Service('storage')


if __name__ == '__main__':
    log = logging.getLogger('cocaine.tools.tools')
    log.setLevel(logging.DEBUG)
    log.propagate = False
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter('[%(asctime)s] %(name)s:%(levelname)-8s: %(message)s')
    ch.setFormatter(formatter)
    log.addHandler(ch)

    a1 = AppUploadFromRepositoryAction(storage, **{'url': 'git+file:///Users/esafronov/mock_repo/repo_echo'})
    a2 = AppUploadFromRepositoryAction(storage, **{'url': 'git+file:///Users/esafronov/mock_repo/repo_echo'})
    a3 = AppUploadFromRepositoryAction(storage, **{'url': 'git+file:///Users/esafronov/mock_repo/repo_echoWRONG'})
    a4 = AppUploadFromRepositoryAction(storage, **{'url': 'git+file:///Users/esafronov/mock_repo/repo_echo'})
    a5 = AppUploadFromRepositoryAction(storage, **{'url': 'git+file:///Users/esafronov/mock_repo/repo_echo'})
    # Run all of them simultaneously
    r = a1.execute().run()#get(20.0)
    r = a2.execute().run()
    r = a3.execute().run()
    r = a4.execute().run()
    r = a5.execute().run()
    IOLoop.instance().start()
    # print('R', r)