from tornado.ioloop import IOLoop

from cocaine import concurrent
from cocaine.services import Service

__author__ = 'Evgeny Safronov <division494@gmail.com>'


@concurrent.engine
def ping(message):
    try:
        response = [0, 0, 0, 0]
        channel = echo.enqueue('ping')
        response[0] = yield channel.read()
        response[1] = yield channel.write(message)
        response[2] = yield channel.read()
        response[3] = yield channel.write('Bye.')
        print(response)
        assert response == ['Hi!', 'Whatever.', 'Another message.', 'Bye.']
    except Exception as err:
        print(repr(err))
    finally:
        IOLoop.current().stop()


if __name__ == '__main__':
    echo = Service('echo')
    ping('Whatever.')
    IOLoop.current().start()