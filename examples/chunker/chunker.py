#!/usr/bin/env python
import msgpack

from cocaine.server.worker import Worker

__author__ = 'EvgenySafronov <division494@gmail.com>'


def chunker(request, response):
    chunks = yield request.read()
    try:
        chunks = int(msgpack.loads(chunks))
    except ValueError:
        chunks = int(chunks)

    for num in xrange(chunks):
        response.write(msgpack.dumps('{0:-<1024}'.format(num)))
    response.write(msgpack.dumps('Done'))
    response.close()

W = Worker()
W.run({'spam': chunker})