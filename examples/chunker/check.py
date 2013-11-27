#!/usr/bin/env python
import os
from tornado.ioloop import IOLoop
from cocaine import concurrent
import msgpack
import sys
from cocaine.protocol import ChokeEvent

from cocaine.services import Service

__author__ = 'EvgenySafronov <division494@gmail.com>'


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print('Usage: chunker.py NUMBER_OF_CHUNKS')
        exit(os.EX_USAGE)

    @concurrent.engine
    def fetchAll():
        yield service.connect()
        df = service.enqueue('spam', str(sys.argv[1]))
        size = 0
        counter = 0
        try:
            while True:
                ch = yield df
                chunk = msgpack.loads(ch)
                size += len(chunk)
                counter += 1
                # print(counter, len(chunk), size)
                if chunk == 'Done':
                    break
        except ChokeEvent:
            pass
        except Exception as err:
            print(err)
        finally:
            IOLoop.current().stop()


    service = Service('chunker')
    fetchAll()
    IOLoop.current().start()
    print('Done')
