#!/usr/bin/env python
# coding=utf-8
import msgpack
import sys
from cocaine.futures.chain import Chain
from cocaine.services import Service

__author__ = 'EvgenySafronov <division494@gmail.com>'


if __name__ == '__main__':
    def fetchAll():
        chunk = yield service.enqueue('chunkMe', str(sys.argv[1]))
        chunk = msgpack.loads(chunk)
        size = len(chunk)
        counter = 0
        while True:
            ch = yield
            chunk = msgpack.loads(ch)
            size += len(chunk)
            counter += 1
            print(counter, len(chunk), size)
            if chunk == 'Done':
                break

    service = Service('Chunker')
    c = Chain([fetchAll])
    c.get()
