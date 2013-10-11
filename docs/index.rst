..

:Authors:
    Evgeny Safronov <division494@gmail.com>,
    (Other contributors as noted in the AUTHORS file)


Cocaine
===================
What is Cocaine? It's an open-source cloud platform enabling you to build your own PaaS clouds using simple yet
effective dynamic components.

* Page on github: https://github.com/cocaine/cocaine-core

This documentation is for cocaine-framework-python.

* Page on PyPI: https://pypi.python.org/pypi/cocaine
* Repository: https://github.com/cocaine/cocaine-framework-python
* Requires at least Python 2.6


More documentation
-------------------

.. toctree::
   :maxdepth: 1

   cocaine


Features
-------------------

* Possibility to write cocaine workers
* Wide support of asynchronous event-driven usage
* Ready for usage with cloud services
* Lot of examples included
* Provided with cocaine-tools and embedded cocaine proxy
* PyPy support


Quick example
-------------------
Here's some extremely useful Cocaine app written in Python::

    #!/usr/bin/env python

    from cocaine.services import Service
    from cocaine.worker import Worker

    storage = Service("storage")

    def process(value):
        return len(value)

    def handle(request, response):
        key = yield request.read()
        value = yield storage.read("collection", key)

        response.write(process(value))
        response.close()

    Worker().run({
        'calculate_length': handle
    })