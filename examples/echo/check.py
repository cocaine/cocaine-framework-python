from tornado.ioloop import IOLoop

from cocaine import concurrent
from cocaine.services import Service

__author__ = 'Evgeny Safronov <division494@gmail.com>'


@concurrent.engine
def ping(message):
    try:
        channel = echo.enqueue('ping')
        response = yield channel.write(message)
        print(response)
    except Exception as err:
        print(err)
    finally:
        IOLoop.current().stop()


if __name__ == '__main__':
    echo = Service('echo')
    ping('Hi!')
    IOLoop.current().start()