Packages
====================================

Package cocaine
------------------------------------
.. automodule:: cocaine.exceptions
   :members:
   :noindex:

Package cocaine.asio
------------------------------------
.. automodule:: cocaine.asio.ev
   :members:
   :noindex:


.. automodule:: cocaine.asio.pipe
   :members:
   :noindex:


.. automodule:: cocaine.asio.service
   :members:
   :noindex:


Package cocaine.futures
------------------------------------
.. automodule:: cocaine.futures.chain
   :members:
   :noindex:


Cocaine Framework API
====================================


Method `get`
------------------------------------

**Use Case**
    We want to create some script to test some cocaine service.


**Solution**
    All service's methods returns `Chain` object instances. You can use `get` method from it.


**Example**
    Let's get all application names from `node` service and print them::

        from cocaine.services import Service
        node = Service('node')
        apps = node.list().get()
        print(apps)


**Comments**
    This method blocks execution of the current client code until at least one chunk will be received or an exception
    will be thrown.
    If succeed there is chunk returned from method, otherwise an exception will be reraised.

    Timeout can be specified by passing keyword argument:

    >>> apps = node.list().get(timeout=1.0)

    .. note:: This method starts event loop, and stops it after chunk receiving. If the current event loop is running
              when `get` method invoked, then it won't be stopped. Anyway, it is not recommended to mix asynchronous
              and synchronous usage of services, because there are other mechanism to deal with it while event loop is
              running.
    .. warning:: Use `get` method only in scripts!


Yield statement
------------------------------------

**Use Case**
    We want to start asynchronous execution of some function or method and receive program control after it is
    finished.


**Solution**
    Use python's **yield** statement in `Chain` context.


**Example**
    Let's get all application names from `node` service and print them while event loop is running (maybe in
    `Worker` context or in some other asynchronous event)::

        from tornado.ioloop import IOLoop
        from cocaine.futures import chain
        from cocaine.services import Service

        node = Service('node')

        @chain.source
        def magic():
            apps = yield node.list()
            print(apps)

        magic()
        IOLoop.current().start()

    You can also use tornado and python 3.3 futures in `Chain` context. Let's download list of pages simultaneously
    and print response time of each::

        from tornado.ioloop import IOLoop
        from tornado.httpclient import AsyncHTTPClient
        from cocaine.futures import chain
        client = AsyncHTTPClient()

        @chain.source
        def downloadInternet(url):
            response = yield client.fetch(url)
            print(response.request.url, response.request_time)

        urls = [
            'http://yandex.ru',
            'http://www.google.ru',
            'http://www.google.com',
            'https://cocaine.readthedocs.org/en/latest/',
            'https://github.com/cocaine/cocaine-core',
            'https://github.com/cocaine/cocaine-framework-native',
            'https://github.com/cocaine/cocaine-framework-python',
            'https://github.com/cocaine/cocaine-plugins',
            'http://www.tornadoweb.org/en/stable/httpclient.html',
        ]

        for url in urls:
            downloadInternet(url)
        IOLoop.current().start()

    When it is done, there will be sorted list of urls with its response time printed. Note, that the order of urls in
    the result list is not equal with `urls` list.


**Comments**
    This is typical usage of cocaine python framework.

    To simplify code, there is `@chain.source` decorator which just patch function and creates `Chain` object from it.
    Decorated function will be executed automatically when event loop is started.

    While in `Chain` context we can use **yield** statement on any callable object that returns
    `cocaine.futures.Future` objects or its heirs, `cocaine.futures.chain` objects, python futures
    (including tornado futures) or any simple objects.

    When asynchronous operation completed, program control will be returned to the **yield** statement,
    returning actual result. If some exception is thrown while processing asynchronous function,
    it will be rethrown to the client side just after **yield** statement, so prepare to catch it.
    If not caught, it will walk down to the event loop and will be lost forever.

    .. note:: If you want to write cocaine applications, it is recommended to use **yield** way.
    .. note:: If you need more examples check `cocaine.tools` package - you can find there a lot of real usage of
              asynchronous chain API.
