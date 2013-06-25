#!/usr/bin/env python
import msgpack

from cocaine.worker import Worker
from cocaine.logging import Logger

__author__ = 'EvgenySafronov <division494@gmail.com>'

log = Logger()


def chunker(request, response):
    chunks = 100 * 1024
    leData = [1024 * str(i) for i in xrange(chunks)]
    for num in xrange(chunks):
        response.write(msgpack.dumps(leData[num]))
    response.write(msgpack.dumps('Done'))
    response.close()

W = Worker()
W.run({'chunkMe': chunker})