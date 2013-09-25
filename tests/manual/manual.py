import os
from cocaine.futures import chain
import msgpack
import sys
from tornado.ioloop import IOLoop

from cocaine.exceptions import ChokeEvent
from cocaine.services import Service


__author__ = 'EvgenySafronov <division494@gmail.com>'


def collect_all(future):
    try:
        msgpack.loads(future.get())
    except ChokeEvent:
        IOLoop.current().stop()


def then_api():
    c = service.enqueue('chunkMe', msgpack.dumps(str(sys.argv[1])))
    c.then(collect_all)
    return c


@chain.source
def yield_api():
    try:
        chunk = yield service.enqueue('chunkMe', msgpack.dumps(str(sys.argv[1])))
        chunk = msgpack.loads(chunk)
        # size = len(chunk)
        # counter = 0
        while True:
            ch = yield
            chunk = msgpack.loads(ch)
            # print(ch)
            # size += len(chunk)
            # counter += 1
            # print(counter, len(chunk), size)
            # if chunk == 'Done':
            #     break
    except ChokeEvent:
        IOLoop.current().stop()


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print('Usage: chunker.py NUMBER_OF_CHUNKS')
        exit(os.EX_USAGE)

    service = Service('chunker')
    try:
        then_api()
        # yield_api()
        IOLoop.current().start()
    except ChokeEvent:
        print('Done')
