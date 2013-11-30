#!/usr/bin/env python
import os
import sys
from cocaine.protocol import ChokeEvent

import msgpack

from tornado.ioloop import IOLoop

from cocaine import concurrent
from cocaine.services import Service

__author__ = 'EvgenySafronov <division494@gmail.com>'


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print('Usage: chunker.py NUMBER_OF_CHUNKS')
        exit(os.EX_USAGE)

    @concurrent.engine
    def test():
        deferred = service.enqueue('spam', str(sys.argv[1]))
        try:
            while True:
                chunk = yield deferred
                if chunk == 'Done':
                    break
        except ChokeEvent:
            pass
        except Exception as err:
            print('Error: {0}'.format(err))
        finally:
            loop.stop()

    service = Service('chunker')
    df = test()
    loop = IOLoop.current()
    loop.start()
    print('Done')
