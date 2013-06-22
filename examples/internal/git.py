from tornado.ioloop import IOLoop
from cocaine.services import Service
from cocaine.tools.tools import AppUploadFromRepositoryAction


__author__ = 'EvgenySafronov <division494@gmail.com>'


storage = Service('storage')


if __name__ == '__main__':
    a1 = AppUploadFromRepositoryAction(storage, **{'url': 'git+file:///Users/esafronov/mock_repo/repo_echo'})
    a2 = AppUploadFromRepositoryAction(storage, **{'url': 'git+file:///Users/esafronov/mock_repo/repo_echo'})
    a3 = AppUploadFromRepositoryAction(storage, **{'url': 'git+file:///Users/esafronov/mock_repo/repo_echo'})
    # Run all of them simultaneously
    r = a1.execute().run()
    r = a2.execute().run()
    r = a3.execute().run()
    IOLoop.instance().start()
    # print('R', r)