#!/usr/bin/env python
import msgpack

from cocaine.worker import Worker
from cocaine.logging import Logger

__author__ = 'EvgenySafronov <division494@gmail.com>'

log = Logger()

def chunker(request, response):
    for num in xrange(5):
        response.write(msgpack.dumps(num))
        log.info('Written: {0}'.format(num))
    response.close()

W = Worker()
W.run({'chunkMe': chunker})