#!/usr/bin/env python

import logging
import asyncio
import pprint

from cocaine.services.base import Locator, Service
from cocaine.concurrent import ChokeEvent

log = logging.getLogger()
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
log.addHandler(ch)
log.setLevel(logging.INFO)


@asyncio.coroutine
def main():
    # Try locator
    l = Locator()
    rx, tx = yield l.resolve("logging")
    resolve_info = yield rx.get()
    pprint.pprint(resolve_info)

    # Try application. Take a look into w.py
    app = Service("rbecho")
    arx, atx = yield app.enqueue("echo")
    for i in xrange(0, 10):
        yield atx.write("PING %d" % i)
        answer = yield arx.get()
        log.info("On ping response %s", answer)

    try:
        yield atx.write("DONE")
        answer = yield arx.get()
    except ChokeEvent:
        log.info("Queue is empty. Done")
    except Exception as err:
        log.error(err)

    # Logger
    s = Service("logging")
    yield s.emit(1, "main", "blabla")

loop = asyncio.get_event_loop()
loop.set_debug(logging.INFO)
asyncio.async(main())
loop.run_forever()
