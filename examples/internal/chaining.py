from __future__ import absolute_import
import logging
from cocaine.futures.chain import ChainFactory
import time
from tornado.ioloop import IOLoop
from cocaine.services import Service

__author__ = 'EvgenySafronov <division494@gmail.com>'


def func():
    c = node.info()
    c.then(handle).run()


def handle(result):
    print "Handle", result.obj


def func2():
    print 'AA'
    try:
        info1 = yield node.info()
    except Exception as err:
        print "ERRR", err
    info2 = yield node.info()
    print(info1, info2)

def func3(args):
    print "Start"
    s = Service("storage")
    try:
        k = yield s.write("A", "A", "KKKKKKKKKKKKKKKKKKKKKKKKKKKKKKK", [])
    except Exception as err:
        print err
    print "END"


if __name__ == '__main__':
    log = logging.getLogger(__name__)
    #chainLog = logging.getLogger('cocaine.futures.chain')
    log.setLevel(logging.DEBUG)
    #chainLog.setLevel(logging.DEBUG)


    node = Service('node')
    #func()

    ChainFactory([func2, func3]).run()
    loop = IOLoop.instance()
    loop.add_timeout(time.time() + 2, lambda: loop.stop() )
    loop.start()

