#!/usr/bin/env python

import logging
import asyncio

from cocaine.services.base import Locator

logging.basicConfig()
log = logging.getLogger("asyncio")


@asyncio.coroutine
def main():
    l = Locator()
    deffered = yield l.resolve("node")
    try:
        result = yield deffered.get()
        print("Chunk: %s" % result)
    except Exception:
        pass

    raw_input("Restart runtime. Press enter")

    deffered = yield l.resolve("node")
    try:
        result = yield deffered.get()
        print("Chunk: %s" % result)
    except Exception:
        pass


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
    loop.close()
