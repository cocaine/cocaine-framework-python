# coding=utf-8
from tornado.ioloop import IOLoop
from cocaine.services import Service

__author__ = 'EvgenySafronov <division494@gmail.com>'


if __name__ == '__main__2':
    def on(chunk):
        print('Response received - {0}'.format(chunk))
        loop.stop()

    def error(exception):
        print('Error received - {0}'.format(exception))
        loop.stop()

    service = Service('Echo')
    future = service.invoke('doIt', 'SomeMessage')
    future.bind(on, error)
    loop = IOLoop.instance()
    loop.start()

if __name__ == '__main__':
    service = Service('Echo')
    for chunk in service.perform_sync('invoke', 'doIt', 'SomeMessage'):
        print('Response received - {0}'.format(chunk))