#!/usr/bin/env python
import os
import msgpack
import sys

from cocaine.exceptions import ChokeEvent
from cocaine.futures.chain import Chain
from cocaine.services import Service

__author__ = 'EvgenySafronov <division494@gmail.com>'


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print('Usage: chunker.py NUMBER_OF_CHUNKS')
        exit(os.EX_USAGE)

    def fetchAll():
        chunk = yield service.enqueue('chunkMe', str(sys.argv[1]))
        # chunk = msgpack.loads(chunk)
        # size = len(chunk)
        # counter = 0
        while True:
            ch = yield
            # chunk = msgpack.loads(ch)
            # size += len(chunk)
            # counter += 1
            # print(counter, len(chunk), size)
            # if chunk == 'Done':
            #     break

    service = Service('Chunker')
    c = Chain([fetchAll])
    try:
        c.get()
    except ChokeEvent:
        print('Done')
