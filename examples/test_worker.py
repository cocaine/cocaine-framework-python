#! /usr/bin/env python

from cocaine.worker import Worker
from cocaine.decorators import *
#from cocaine.decorators import *
from cocaine.services import Log

from hashlib import sha512

l = Log()
l.info("INFO")
l.debug("DEBUG")
l.error("ERROR")
l.warn("WARN")

@http
def http_ok(response):
    headers = yield
    result = "<html><head>Hash</head>%s</html>\r\n" % sha512(str(headers)).hexdigest()
    #l.debug(result)
    response.write_head( 200, {'Content-Type' : 'text/plain'})
    response.write(result)
    response.close()

@fs
def fs_ok(response):
    stats = yield
    l.info("fs_ok")
    l.info(stats)
    response.close()

def fs_func(request, response):
    l.info("fs_func")
    l.info(request)
    response.close()


W = Worker()
W.on("hash", http_ok)
W.on("fs", fs_ok)
W.on("fs2", fs_func)
W.run()
