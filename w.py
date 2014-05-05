#!/usr/bin/env python

import asyncio

from cocaine.worker import Worker


w = Worker(app="app", uuid="a", endpoint="enp",
           heartbeat_timeout=2, disown_timeout=1)


@asyncio.coroutine
def echo(request, response):
    yield asyncio.sleep(1)
    inp = yield request.read(timeout=1)
    print inp
    response.write(inp)
    response.close()

w.on("echo", echo)
w.run()
