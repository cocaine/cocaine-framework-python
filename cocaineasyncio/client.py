#!/usr/bin/env python

import logging
import asyncio


from cocaine.services.base import Locator

logging.basicConfig()
log = logging.getLogger("asyncio")


@asyncio.coroutine
def simple():
    l = Locator()
    deffered = yield l.resolve("node")
    try:
        result = yield deffered.get()
        log.info("Chunk: %s" % result)
    except Exception as err:
        log.error(repr(err))


@asyncio.coroutine
def chain():
    l = Locator()
    d1 = yield l.resolve("node")
    d2 = yield l.resolve("storage")

    for f in asyncio.as_completed([d1.get(), d2.get()]):
        result = yield asyncio.From(f)
        log.info("Result %s" % result)


@asyncio.coroutine
def waits():
    l = Locator()
    d1 = yield l.resolve("node")
    d2 = yield l.resolve("storage")

    # wait all
    done, pending = yield asyncio.wait([d1.get(),
                                        d2.get(),
                                        asyncio.sleep(1.0)])
    log.info("Done %d. Pending %d", len(done), len(pending))

    # wait with timeout.
    d3 = yield l.resolve("node")
    done, pending = yield asyncio.wait([d3.get(),
                                        asyncio.sleep(5.0)],
                                       timeout=4.0)
    log.info("Done %d. Pending %d", len(done), len(pending))

    # wait with timeout, when the first completes
    # result'll be returned
    d4 = yield l.resolve("node")
    done, pending = yield asyncio.wait([d4.get(),
                                        asyncio.sleep(3.0)],
                                       timeout=4.0,
                                       return_when=asyncio.FIRST_COMPLETED)
    log.info("Done %d. Pending %d", len(done), len(pending))

    d5 = yield l.resolve("node")

    @asyncio.coroutine
    def w():
        res = yield d5.get()
        log.info("Result from w(): %s", res)
        yield asyncio.sleep(4.0)

    try:
        yield asyncio.wait_for(w(), timeout=2)
    except asyncio.TimeoutError as err:
        log.error("%s", repr(err))

    d6 = yield l.resolve("node")
    try:
        yield d6.get(timeout=0.00001)
    except asyncio.TimeoutError as err:
        log.error("%s", repr(err))


@asyncio.coroutine
def main():
    log.info("Start simple example")
    yield simple()
    log.info("Start chain example")
    yield chain()
    log.info("Start a_wait example")
    yield waits()
    loop.stop()


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    asyncio.async(main())
    loop.run_forever()
    loop.close()
