# coding=utf-8
from time import time
import numpy
import objgraph
import sys
import msgpack

from tornado.ioloop import IOLoop, PeriodicCallback

from cocaine.futures.chain import Chain
from cocaine.services import Service

__author__ = 'Evgeny Safronov <division494@gmail.com>'


def example_SynchronousFetching():
    for chunk in service.perform_sync('enqueue', 'doIt', 'SomeMessage'):
        # print('1. example_SynchronousFetching: Response received - {0}'.format(msgpack.loads(chunk)))
        pass
    pass


def example_Synchronous():
    message = service.enqueue('doIt', 'SomeMessage').get()
    # print('2. example_Synchronous: Response received - {0}'.format(msgpack.loads(message)))
    pass


def example_AsynchronousYielding():
    message = yield service.enqueue('doIt', 'SomeMessage')
    message = msgpack.loads(message)
    assert message == 'SomeMessag'
    c.inc()


def example_AsynchronousChaining():
    def printAsynchronousChaining(message):
        assert message.get() == 'SomeMessage'
    s = service.enqueue('doIt', 'SomeMessage')
    s.then(lambda r: msgpack.loads(r.get())).then(printAsynchronousChaining)
    c.inc()


class Counter(object):
    def __init__(self, maxRequests, tickLimit):
        self.requests = 0
        self.start = time()
        self.ticks = 0
        self.tickLimit = tickLimit

        self.maxRequests = maxRequests
        self.finish = self.start

        self.t = []
        self.r = []

    def inc(self):
        # if (self.requests * 100.0 / self.maxRequests) % 1 == 0:
        if (self.requests * 100.0 / self.maxRequests) >= self.tickLimit * self.ticks:
            self.ticks += 1
            self.r.append(self.requests)
            self.t.append(time())
            if len(self.r) > 1 and len(self.t) > 1:
                poly = numpy.polyfit(self.t, self.r, 1)
                elapsed = (self.maxRequests - poly[1]) / poly[0] - time()
            else:
                elapsed = 0
            sys.stdout.write('\rDone: {0} ({1:.1f}%). Elapsed: ~{2:.3f}s'.format(
                self.requests, self.requests * 100.0 / self.maxRequests, elapsed
            ))
            sys.stdout.flush()
        if self.requests == self.maxRequests:
            loop.stop()
        self.requests += 1


if __name__ == '__main__':
    config = {
        'service': {
            'name': 'Echo'
        },
        'benchmark': {
            'interval': 0.01,
            'maxRequests': 100000,
            'tickLimit': 0.1
        },
        'printObjectGraph': False,
        'measureTime': True
    }

    c = Counter(config['benchmark']['maxRequests'], config['benchmark']['tickLimit'])
    service = Service(config['service']['name'])

    if config['printObjectGraph']:
        print('Object graph.')
        objgraph.show_growth()
        print('')

    start = time()

    print('Total requests: {0}'.format(c.maxRequests))
    loop = IOLoop.instance()
    p = PeriodicCallback(lambda: Chain([example_AsynchronousChaining]), config['benchmark']['interval'], io_loop=loop)
    p.start()
    loop.start()
    print('')
    if config['measureTime']:
        stop = time()
        print('Total elapsed: {0:.3f}s'.format(stop - start))

