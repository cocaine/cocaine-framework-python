from cocaine.services import Service
from cocaine.tools.tools import AppUploadFromRepositoryAction


__author__ = 'EvgenySafronov <division494@gmail.com>'


storage = Service('storage')


if __name__ == '__main__':
    a = AppUploadFromRepositoryAction(storage, **{'url': 'git+file:///Users/esafronov/mock_repo/repo_echo'})
    r = a.execute().get(timeout=60.0)
    print('R', r)