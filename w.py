#!/usr/bin/env python

import asyncio

from cocaine.worker import Worker

w = Worker()


@asyncio.coroutine
def echo(request, response):
    while True:
        c = yield request.read()
        if c != "DONE":
            response.write(str(c))
        else:
            break
    response.close()

w.on("echo", echo)
w.run()
