from tornado.ioloop import IOLoop

from cocaine import concurrent
from cocaine.services import Service
from cocaine.services.logger import Logger

__author__ = 'Evgeny Safronov <division494@gmail.com>'

log = Logger('omg')
print(log.verbosity)
log.emit(3, 'Hi, %s', 'hui pizda')


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
        print(err)
    finally:
        IOLoop.current().stop()


if __name__ == '__main__':
    echo = Service('echo')
    ping('Whatever.')
    IOLoop.current().start()