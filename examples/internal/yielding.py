from __future__ import absolute_import
import logging
import time
from tornado.ioloop import IOLoop
from cocaine.futures import Future
from cocaine.futures.chain import Chain

__author__ = 'EvgenySafronov <division494@gmail.com>'


class Fut(Future):
        def __init__(self, yields=1):
            self.yields = yields
            self.pos = 0

        def bind(self, callback, errorback=None, on_done=None):
            self.cb = callback
            self.eb = errorback
            self.db = on_done
            self.start()

        def start(self, timeout=0.1):
            loop = IOLoop.instance()
            for pos, value in enumerate(self.yields):
                loop.add_timeout(time.time() + timeout + pos * 0.1, self.inv)

        def inv(self):
            result = self.yields[self.pos]
            self.pos += 1
            return self.cb(result)


class SomeErrorServiceError(Exception):
    pass


class EFut(Future):
        def __init__(self, value):
            self.cb = None
            self.eb = None
            self.value = value

        def bind(self, callback, errorback=None, on_done=None):
            self.cb = callback
            self.eb = errorback
            self.db = on_done
            self.start()

        def doBad(self):
            try:
                raise SomeErrorServiceError('Bad!')
            except Exception as err:
                self.eb(err)

        def start(self, timeout=0.1):
            IOLoop.instance().add_timeout(time.time() + timeout, self.doBad)


class ServiceMock(object):
    def __init__(self, yields=None):
        self.yields = yields

    def execute(self):
        return Fut(self.yields)


class SomeErrorService(object):
    def __init__(self, value):
        self.value = value

    def execute(self):
        return EFut(self.value)


def f1():
    return 1


def f2(result):
    return 'r320r353475734854'


def step1():
    log.info('Invoking service that returns exactly 3 chunks. We have to get it all!')
    r10 = yield ServiceMock(yields=(0, 10, 20)).execute()
    r11 = yield
    r12 = yield
    log.info('Result: {0}'.format((r10, r11, r12)))
    assert r10 == 0
    assert r11 == 10
    assert r12 == 20

    log.info('>>> Invoking service that returns exactly 1 chunk')
    r20 = yield ServiceMock(yields=(2, )).execute()
    log.info('>>> Result: {0}'.format(r20))
    assert r20 == 2

    log.info('>>> Invoking service that returns exactly 1 chunk')
    r30 = yield ServiceMock(yields=(3, )).execute()
    log.info('>>> Result: {0}'.format(r30))
    assert r30 == 3

    # Doesn't seems to be adequate
    log.info('>>> Just yielding some integer. Doesn\'t seems to be adequate, but who knows ...')
    r4 = yield 4
    log.info('>>> Result: {0}'.format(r4))
    assert r4 == 4

    log.info('>>> Here we raise exception in service')
    try:
        r5 = yield SomeErrorService(1).execute()
        log.error('>>> Something goes wrong! You should never see this message!')
    except SomeErrorServiceError as err:
        log.info('>>> Result: {0}'.format(err))

    result = yield Chain().then(f1).then(f2)
    print(result, '>>> RESULT!!!')

    raise Exception('12345')

    yield 'Return'


def step2(result):
    try:
        log.info('Step 2. Input value must be "Return": {0}'.format(result.get()))
        assert result.get() == 'Return'
    except Exception as err:
        assert err.message == '12345'
    return 'Fuck you all!'


def finish(value):
    try:
        log.info('Finished! - {0}'.format(value.get()))
    except Exception as err:
        log.error('Error caught in finish method - {0}'.format(err))

if __name__ == '__main__':
    log = logging.getLogger(__name__)
    chainLog = logging.getLogger('cocaine.futures.chain')
    log.setLevel(logging.DEBUG)
    chainLog.setLevel(logging.DEBUG)

    ChainFactory().then(step1).then(step2).then(finish).run()
    loop = IOLoop.instance()

    def timeout():
        print('TIMEOUT')
        loop.stop()
    loop.add_timeout(time.time() + 2.0, timeout)
    loop.start()
