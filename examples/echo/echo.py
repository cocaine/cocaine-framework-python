#!/usr/bin/env python
import msgpack
import time

from cocaine.worker import Worker
from cocaine.logging import Logger

__author__ = 'EvgenySafronov <division494@gmail.com>'

log = Logger()


def echo(request, response):
    message = yield request.read()
    log.debug('Message received: \'{0}\'. Sending it back ...'.format(message))
    response.write(message)
    response.close()


W = Worker()
W.run({
    'ping': echo,
})
