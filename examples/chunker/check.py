# coding=utf-8
from tornado.ioloop import IOLoop
from cocaine.services import Service

__author__ = 'EvgenySafronov <division494@gmail.com>'


if __name__ == '__main__':
    def on(chunk):
        print('Response received - {0}'.format(chunk))

    def error(reason):
        print('Error received - {0}'.format(reason))

    service = Service('Chunker')
    future = service.invoke('chunkMe', '1')
    future.bind(on, error)
    loop = IOLoop.instance()
    loop.start()