# coding=utf-8
import sys

from cocaine.futures.chain import Chain
import msgpack
from cocaine.services import Service

__author__ = 'Evgeny Safronov <division494@gmail.com>'


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
    Chain([example_AsynchronousYielding]).wait()
    example_AsynchronousChaining()\
        .then(lambda r: msgpack.loads(r.get()))\
        .then(lambda r: sys.stdout.write('example_AsynchronousChaining: Response received - {0}\n'.format(r.get())))\
        .wait()
    sys.stdout.flush()