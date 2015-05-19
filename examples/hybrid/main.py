#!/usr/bin/env python

from cocaine.worker import Worker
from cocaine.services import Service
from cocaine.decorators import http

NAMESPACE = "testnamespace"
KEY = "testkey"

storage = Service("storage")


def write(request, response):
    data = yield request.read()
    try:
        channel = yield storage.write(NAMESPACE, KEY, data, [])
        yield channel.rx.get()
        response.write("Ok")
    except Exception as err:
        response.error(-100, repr(err))
    finally:
        response.close()


def read(request, response):
    try:
        channel = yield storage.read(NAMESPACE, KEY)
        data = yield channel.rx.get()
        response.write(data)
    except Exception as err:
        response.error(-100, repr(err))
    finally:
        response.close()


@http
def http_read(request, response):
    yield request.read()
    with response:
        channel = yield storage.read(NAMESPACE, KEY)
        res = yield channel.rx.get()
        response.write(res)


if __name__ == '__main__':
    W = Worker()
    W.run({"write": write,
           "read": read,
           "http": http_read})
