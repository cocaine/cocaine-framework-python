#! /usr/bin/env python

from hashlib import sha512

from cocaine.worker import Worker
from cocaine.logger import Logger
from cocaine.service.services import Service
from cocaine.exceptions import *

L = Logger()

urlfetcher_service = Service("urlfetch")
storage_service = Service("storage")

def example(request, response):
    L.info("INITIALIZE FUNCTION")
    try:
        ls = yield storage_service.list()
        L.info("From storage: %s" % ls)
    except ServiceError as err:
        L.error("S: %s" % err)
        ls = yield storage_service.list("manifests")
        L.info("From storage: %s" % ls)

    L.info("Now yield")
    yield
    L.info("After yield")

    L.info("Request www.ya.ru")
    webpage = yield urlfetcher_service.get("www.ya.ru",{}, True)

    chunk_from_cloud = yield request.read()
    L.info("from dealer: %s" % chunk_from_cloud)
    try:
        chunk_from_cloud = yield request.read()
        L.info("from dealer: %s" % chunk_from_cloud)
    except RequestError as err:
        L.error("R: %s" % err)

    L.info("Request www.google.ru")
    webpage = yield urlfetcher_service.get("www.google.ru",{}, True)

    response.write("EXAMPLE")
    response.close()

def nodejs(request, response):
    """ Nodejs style """
    def on_url(chunk):
        def on_request(chunk):
            L.info("Request chunk: %s" % chunk)
            response.write("NODEJS")
            response.close()
        L.info("Webpage hash: %s" % sha512(chunk).hexdigest())
        future = request.read()
        future(on_request)

    def errorback(error):
        L.info("errorback")
        L.info(error)
        future = urlfetcher_service.get("www.ya.ru",{}, True)
        future(on_url)

    L.info("INITIALIZE FUNCTION")
    future = urlfetcher_service.get()
    future(on_url, errorback)

W = Worker()
W.on("hash", example)
W.on("nodejs", nodejs)
W.run()
