#!/usr/bin/env python
# coding=utf-8
import msgpack
from cocaine.futures.chain import Chain
from cocaine.services import Service

__author__ = 'EvgenySafronov <division494@gmail.com>'


if __name__ == '__main__':
    def fetchAll():
        leData = []
        chunk = yield service.enqueue('chunkMe', '1')
        leData += msgpack.loads(chunk)
        size = len(chunk)
        counter = 1
        while True:
            ch = yield
            chunk = msgpack.loads(ch)
            size += len(chunk)
            counter += 1
            print(counter, len(chunk), size)#, chunk)
            if chunk == 'Done':
                break
            leData += chunk

        print(len(leData))

    service = Service('Chunker')
    c = Factory([fetchAll])
    c.get(timeout=60.0)
