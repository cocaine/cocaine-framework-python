#!/usr/bin/env python

import asyncio

from cocaine.worker import Worker
from cocaine.services import Service


w = Worker(app="app", uuid="a", endpoint="enp",
           heartbeat_timeout=2, disown_timeout=1)

node = Service("node")


@asyncio.coroutine
def echo(request, response):
    yield asyncio.sleep(1)
    inp = yield request.read(timeout=1)
    print inp
    fut = yield node.list()
    result = yield fut.get()
    print result
    response.write(result)
    response.close()

w.on("echo", echo)
w.run()
