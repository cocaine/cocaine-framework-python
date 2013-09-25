import subprocess
import sys
from cocaine.futures import chain
import msgpack
from tornado.ioloop import IOLoop
from cocaine.asio.service import Service
from cocaine.exceptions import ChokeEvent

__author__ = 'Evgeny Safronov <division494@gmail.com>'


ticks = 1
num = '1000000'

s = Service('Chunker')


def ideal():
    for _ in s.perform_sync('enqueue', 'chunkMe', num):
        pass


def collect_all(future):
    try:
        msgpack.loads(future.get())
    except ChokeEvent:
        IOLoop.current().stop()


def then_api():
    c = s.enqueue('chunkMe', num)
    c.then(collect_all)
    return c

@chain.source
def yield_api():
    try:
        chunk = yield s.enqueue('chunkMe', num)
        msgpack.loads(chunk)
        while True:
            ch = yield
            msgpack.loads(ch)
    except ChokeEvent:
        IOLoop.current().stop()


def benchmark():
    # then_api()
    yield_api()
    IOLoop.current().start()

if __name__ == '__main__':
    import timeit
    time_ideal = timeit.timeit('ideal()', setup='from __main__ import ideal', number=ticks)
    print('Summary ideal {0:.3f}s'.format(time_ideal))

    time_real = timeit.timeit('benchmark()', setup='from __main__ import benchmark', number=ticks)
    print('Summary real {0:.3f}s'.format(time_real))

    print(time_real / time_ideal)

    #  raw  real         -logs-        -future locks-      -stream locks-
    # 33.08|89.34|2.70    ON               ON                  ON
    # 24.12|87.88|3.64    ON               ON                  OFF
    # 31.74|77.12|2.43    OFF              ON                  ON
    # 23.73|63.86|2.69    OFF              OFF                 OFF
    # 32.71|58.26|1.78    OFF              OFF                 ON
    ## Refactoring
    # 32.32|48.05|1.49    OFF              OFF                 ON


# `then` way
# Summary ideal 31.347s
# Summary real 32.475s
# 1.03596578725

# `yield` way
# Summary ideal 31.934s
# Summary real 36.671s
# 1.14835817715