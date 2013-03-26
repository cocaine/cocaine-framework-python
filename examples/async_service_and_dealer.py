#! /usr/bin/env python

from cocaine.worker import Worker
from cocaine.decorators import *
from cocaine.service.urlfetcher import Urlfetcher
from cocaine.service.logger import Log

from hashlib import sha512

#l = Log()
#l.info("INFO")
#l.debug("DEBUG")
#l.error("ERROR")
#l.warn("WARN")

U = Urlfetcher()

def http_ok(request, response):
    print "INITIALIZE FUNCTION." 
    print "Request www.ya.ru"
    webpage = yield U.get("www.ya.ru")
    print webpage
    chunk_from_cloud = yield request.read()
    print "from dealer:", chunk_from_cloud
    print "Request www.google.ru"
    webpage = yield U.get("www.google.ru")
    print webpage
    response.push("ANSWER")
    response.close()


W = Worker()
W.on("hash", http_ok)
W.run()
