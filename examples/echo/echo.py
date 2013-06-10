from cocaine.worker import Worker
from cocaine.logging import Logger

__author__ = 'EvgenySafronov <division494@gmail.com>'

log = Logger()

def example(request, response):
    log.debug('INITIALIZE FUNCTION')
    for r in request.read():
        log.debug(r)
    response.close()

W = Worker()
W.run()