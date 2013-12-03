import subprocess

from tornado.ioloop import IOLoop

from cocaine.futures import Deferred, chain

__author__ = 'EvgenySafronov <division494@gmail.com>'


def async_subprocess(command, callbacks=None, cwd=None, io_loop=None):
    """Run subprocess asynchronously and get bound `Deferred` object.

    This function runs separate subprocess `command` and attaches to the standard output stream (`stdout`) and
    error stream (`stderr`), providing ability to read them asynchronously.

    This can be useful when running multiple subprocesses simultaneously, e.g. in web server.

    You can attach up to two callbacks as list for `callbacks` parameter, first of them will be callback for `stdout`,
    second - for `stderr`.

    For example::

        engine.subprocess(['echo 123'], callbacks=[sys.stdout.write, None])

    means `sys.stdout` function as callback for `stdout` and there will be no callback for `stderr`.

    Returned `Deferred` object will trigger immediately after subprocess is finished, transferring error code as
    parameter. If process exits with error code differed from 0 an `IOError` exception will be thrown.

    An subprocess pipe exception will be raised if subprocess can not be started.

    .. note:: You can `yield` this function in `engine.asynchronous` context.

    :param command: command for subprocess to start, same as `subprocess.Popen` first argument.
    :param callbacks: list of two callbacks for `stdout` and `stderr` respectively. If you don't want to attach
                      any callback, you can pass `None` as function.
    :param cwd: current working directory for subprocess.
    :param io_loop: tornado event loop, current by default.
    """
    io_loop = io_loop or IOLoop.current()
    PIPE = subprocess.PIPE
    process = subprocess.Popen(command, shell=True, stdin=PIPE, stdout=PIPE, stderr=PIPE, close_fds=True, cwd=cwd)

    fhs = [process.stdout, process.stderr]
    deferred = Deferred()

    def create_handler(fh, callback):
        def handle(fd, events):
            assert events == io_loop.READ
            data = fh.readline()
            if callback is not None and data:
                callback(data)

            if process.poll() is not None:
                io_loop.remove_handler(fd)
                if process.returncode == 0:
                    deferred.trigger(process.returncode)
                else:
                    deferred.error(IOError(process.returncode))
        return handle

    for fh, callback in zip(fhs, callbacks):
        io_loop.add_handler(fh.fileno(), create_handler(fh, callback), io_loop.READ)
    return deferred


def asynchronous(func):
    """Decorates callable object as asynchronous and make possible to yield framework's deferreds and futures in it.

    Decorator transforms any callable object, making deferred callable object. In fact, invocation event is pushed
    in the event loop, which calls it later as it turn comes.

    Decorated objects gain ability to `yield` all framework's futures and deferreds as like as tornado and python 3.3.
    futures.

    As the callable object becomes deferred, it can be `yielded` in another `asynchronous` decorated function, making
    possible to create large chains of asynchronous invocations.
    """
    return chain.source(func)
