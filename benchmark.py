# coding=utf-8
from time import time
import numpy
import objgraph
import sys

from tornado.ioloop import IOLoop, PeriodicCallback

from cocaine import concurrent
from cocaine.services import Service

__author__ = 'Evgeny Safronov <division494@gmail.com>'


@concurrent.engine
def tickV0():
    try:
        response = yield service.enqueue('pingV0', 'Whatever.')
        assert response == 'Whatever.'
    except Exception as err:
        print(repr(err))
    finally:
        c.inc()


@concurrent.engine
def tickV1():
    try:
        response = [0, 0, 0, 0]
        channel = service.enqueue('pingV1')
        response[0] = yield channel.read()
        response[1] = yield channel.write('SomeMessage')
        response[2] = yield channel.read()
        response[3] = yield channel.write('Bye.')
        assert response == ['SomeMessage', 'Whatever.', 'Another message.', 'Bye.']
        assert response == [0, 'SomeMessage', 0, 0]
    except Exception as err:
        print(err)
    finally:
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
            'name': 'echo'
        },
        'benchmark': {
            'interval': 1,
            'maxRequests': 100000,
            'tickLimit': 0.1
        },
        'printObjectGraph': False,
        'measureTime': True,
        'measureRPS': True
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
    p = PeriodicCallback(tickV0, config['benchmark']['interval'], io_loop=loop)
    p.start()
    loop.start()
    print('')
    if config['measureTime']:
        stop = time()
        print('Total elapsed: {0:.3f}s'.format(stop - start))

    if config['measureRPS']:
        stop = time()
        print('RPS: {0:.3f}'.format(config['benchmark']['maxRequests'] / (stop - start)))

