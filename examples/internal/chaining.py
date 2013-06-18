from __future__ import absolute_import
import functools
from cocaine.futures.chain import ChainFactory
import time
from tornado.ioloop import IOLoop
from cocaine.services import Service

__author__ = 'EvgenySafronov <division494@gmail.com>'


def trackable(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        wrapper.called += 1
        func(*args, **kwargs)
    wrapper.called = 0
    return wrapper


def invokeNodeInfo():
    c = node.info()
    c.then(handle).run()


@trackable
def handle(result):
    print "Handle", result.obj


def func2():
    info1 = yield node.info()
    info2 = yield node.info()
    print(info1, info2)


def func3(args):
    print "Start"
    s = Service("storage")
    yield s.write("A", "A", "A", [])
    print "END"


if __name__ == '__main__':
    node = Service('node')
    invokeNodeInfo()

    def shutdown():
        loop.stop()
        assert handle.called == 1

    ChainFactory([func2, func3]).run()
    loop = IOLoop.instance()
    loop.add_timeout(time.time() + 0.2, shutdown)
    loop.start()

