#! /usr/bin/env python

from hashlib import sha512

from cocaine.worker import Worker
from cocaine.decorators import *
#from cocaine.service.urlfetcher import Urlfetcher
from cocaine.service.logger import Log
from cocaine.service.services import Service
from cocaine.exceptions import *


#l = Log()
#l.info("INFO")
#l.debug("DEBUG")
#l.error("ERROR")
#l.warn("WARN")

urlfetcher_service = Service("urlfetch")
storage_service = Service("storage")

def example(request, response):
    print "INITIALIZE FUNCTION"
    try:
        ls = yield storage_service.list()
        print "From storage: %s" % ls
    except ServiceError as err:
        print "S: %s" % err
        ls = yield storage_service.list("manifests")
        print "From storage: %s" % ls

    print "Request www.ya.ru"
    webpage = yield urlfetcher_service.get("www.ya.ru",{}, True)
    #l.info(sha512(webpage).hexdigest())

    chunk_from_cloud = yield request.read()
    print "from dealer:", chunk_from_cloud
    try:
        chunk_from_cloud = yield request.read()
        print "from dealer:", chunk_from_cloud
    except RequestError as err:
        print "R: %s" % err

    print "Request www.google.ru"
    webpage = yield urlfetcher_service.get("www.google.ru",{}, True)
    #l.info(sha512(webpage).hexdigest())

    print "ANSWER"
    response.write("ANSWER")
    response.close()


W = Worker()
W.on("hash", example)
W.run()
