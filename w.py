#!/usr/bin/env python

from cocaine.worker import Worker


w = Worker(app="app", uuid="a", endpoint="enp",
           heartbeat_timeout=2, disown_timeout=1)


def echo(request, response):
    inp = yield request.read()
    print inp
    response.write(inp)
    response.close()

w.on("echo", echo)
w.run()
