#!/usr/bin/env python

from cocaine.worker import Worker
from cocaine.services import Service

storage = Service("storage")

def write_dummy(request, response):
    req = yield request.read()
    yield storage.write("dummy-namespace", "dummy-key",
                        req, ["dummy-tag"])
    dummy = yield storage.read("dummy-namespace", "dummy-key")
    response.write(dummy)
    response.close()

W = Worker()
W.run({"write_dummy" : write_dummy})
