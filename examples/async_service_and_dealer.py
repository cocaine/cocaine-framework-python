#! /usr/bin/env python

from hashlib import sha512

from cocaine.worker import Worker
from cocaine.logging import Logger
from cocaine.services import Service
from cocaine.exceptions import *
from cocaine.decorators import http, fs


L = Logger()

urlfetcher_service = Service("urlfetch")
storage_service = Service("storage")

import sys

def example(request, response):
    L.info("INITIALIZE FUNCTION")
    try:
        ls = yield storage_service.list()
        L.info("From storage: %s" % str(ls))
    except ServiceError as err:
        L.error("S: %s" % err)
        ls = yield storage_service.list("manifests")
        L.info("From storage: %s" % str(ls))

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

@http
def http(request, response):
    stat = yield request.read()
    L.info("HTTP")
    L.info(stat)
    response.write_head(200, [('Content-type', 'text/plain')])
    response.write("OK")
    response.close()

@fs
def fs(request, response):
    stat = yield request.read()
    L.info("FS")
    L.info(stat)
    response.write("OK")
    response.close()

W = Worker()
#W.on("hash", example)
#W.on("nodejs", nodejs)
#W.on("fs", fs)
W.run({"hash" : example, "fs" : fs})
