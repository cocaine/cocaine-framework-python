# coding=utf-8
from cocaine.services import Service
from cocaine.futures import chain
import socket
import time
from tornado.ioloop import IOLoop

import logging

log = logging.getLogger(__name__)
logging.basicConfig(format='%(levelname)-8s [%(asctime)s]: %(message)s', level=logging.DEBUG)

__author__ = 'EvgenySafronov <division494@gmail.com>'


def f1(result=None):
    log.info('Entered at f1. I am async! My input = {0}'.format(result))
    yield service.find('manifests', ('app',))


def f2(result):
    log.info('Entered at f2. I am async! My input = {0}'.format(result.get()))
    time.sleep(0.5)
    future = service.find('profiles', ('profile',))
    yield future


def f3(result):
    log.info('Entered at f3. I am async! My input = {0}'.format(result.get()))
    future = service.find('runlists', ('runlist',))
    yield future


def f4(result):
    log.info('Entered at f4. I am async! My input = {0}'.format(result.get()))
    future = service.find('manifests', ('app',))
    yield future


#todo: What happens if the function awaits more than one results (via yield), but they aren't going to come
def f5(result):
    log.info('Entered at f5. I am sync! My input = {0}. Sleeping for 1 sec ...'.format(result.get()))
    time.sleep(1.0)
    return 'Just some value from sync function'


@chain.asynchronousCallable
def f6(future, result):
    log.info('Entered at f6. I am async and invoke callback by tornado timeout! My input = {0}'.format(result.get()))
    loop.add_timeout(time.time() + 1.0, lambda: future.ready(10000))


def f7(result):
    log.info('Entered at f7. I am sync and I raise exception! My input = {0}'.format(result.get()))
    raise Exception('Fuck you all!')


def f8(result):
    log.info('Entered at f8. I am async! My input must be an exception')
    try:
        result.get()
        log.info('This should never be seen cause the exception must be thrown one line above')
    except Exception as err:
        log.info('Expected exception - {0}'.format(err))
    future = service.find('manifests', ('app',))
    yield future


def f_finish(result):
    log.info('Entered at f_finish. I am async! My input = {0}'.format(result.get()))
    log.info('Done')
    return None


def main():
    """
    Идея заключается в чем. Допустим, мы хотим оформить интерфейс цепочки асинхронных вызовов таким образом, что
     каждый следующий вызов будет происходить ровно в тот момент, когда будет готов результат предыдущего.
     Пусть наш класс называется Chain и он принимает на вход некую функцию, которую будет выполнять.
     Для того, чтобы он мог узнать, в какой именно момент следует запускать эту функцию, ему необходимо, чтобы кто-то
     указал этот момент. Это может делать предыдущее звено цепочки. Таким образом, мы имеем цепочку следующего вида:
     c1 = Chain(f1, c2)
     c2 = Chain(f2, c3)
     ...
     cn = Chain(fn, None)

     Развернем определение этой цепочки, чтобы код работал:
     cn = Chain(fn, None)
     ...
     c3 = ...
     c2 = Chain(f2, c3)
     c1 = Chain(f1, c2)
     c1.run()

     либо:
     с1 = Chain(f1, Chain(f2, Chain(f3, ...Chain(fn)))...).run()

     Мы ожидаем результат выполнения функций f1, f2 ... fn объект типа Future, который имеет метод
      bind(callback, errorback, on_done) для задания хендлеров. В качестве обработчиков мы назначаем собственные методы
      класса Chain, которые просто вызывают следующее звено цепочки.

    Чтобы запустить выполнение цепочки, надо вызвать метод run, который создаст цепочку обработчиков и вызовет первое
     звено.

    В качестве синтаксического сахара был написан класс ChainFactory, который позволяет писать вышеописанную цепочку
     как:
     ChainFactory().then(f1).then(f2).then(f3).then(f4).then(f5).then(f6).then(f7).then(f8).run()

    Единственное требование к функциям: возвращаемый объект должен иметь метод bind(callback, errorback, on_done).
    """
    pass


if __name__ == '__main__':
    try:
        service = Service('storage', 'localhost', 10053)
        loop = IOLoop.instance()
        log.info('Entering tornado event loop. It will be stopped after 10 seconds')
        chain.ChainFactory().then(f1).then(f2).then(f3).then(f4).then(f5).then(f6).then(f7).then(f8).then(f_finish).run()
        loop.add_timeout(time.time() + 10.0, loop.stop)
        loop.start()
    except socket.error as err:
        log.error('Epic Fail')