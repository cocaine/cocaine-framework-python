# coding=utf-8
import sys
from cocaine.futures.chain import ChainFactory
import msgpack
from cocaine.services import Service

__author__ = 'EvgenySafronov <division494@gmail.com>'


def example_SynchronousFetching():
    for chunk in service.perform_sync('enqueue', 'doIt', 'SomeMessage'):
        print('example_SynchronousFetching: Response received - {0}'.format(msgpack.loads(chunk)))


def example_Synchronous():
    message = service.enqueue('doIt', 'SomeMessage').get()
    print('example_Synchronous: Response received - {0}'.format(msgpack.loads(message)))


def example_AsynchronousYielding():
    message = yield service.enqueue('doIt', 'SomeMessage')
    print('example_AsynchronousYielding: Response received - {0}'.format(msgpack.loads(message)))


def example_AsynchronousChaining():
    return service.enqueue('doIt', 'SomeMessage')


if __name__ == '__main__':
    service = Service('Echo')
    example_SynchronousFetching()
    example_Synchronous()
    ChainFactory([example_AsynchronousYielding]).get(timeout=1)
    example_AsynchronousChaining()\
        .then(lambda r: msgpack.loads(r.get()))\
        .then(lambda r: sys.stdout.write('example_AsynchronousYielding: Response received - {0}'.format(r.get())))\
        .get(timeout=1)