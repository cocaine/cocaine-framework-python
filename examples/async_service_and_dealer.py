#! /usr/bin/env python

from hashlib import sha512

from cocaine.worker import Worker
from cocaine.decorators import *
#from cocaine.service.urlfetcher import Urlfetcher
from cocaine.service.logger import Log
from cocaine.service.services import Service


l = Log()
l.info("INFO")
l.debug("DEBUG")
l.error("ERROR")
l.warn("WARN")

S = Service("urlfetch")

def http_ok(request, response):
    print "INITIALIZE FUNCTION." 
    print "Request www.ya.ru"
    webpage = yield S.get(["www.ya.ru",[], True])
    l.info(sha512(webpage).hexdigest())
    chunk_from_cloud = yield request.read()
    print "from dealer:", chunk_from_cloud
    print "Request www.google.ru"
    webpage = yield S.get(["www.google.ru",[], True])
    l.info(sha512(webpage).hexdigest())
    print "ANSWER"
    response.push("ANSWER")
    response.close()


W = Worker()
W.on("hash", http_ok)
W.run()
