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
* Cocaine-tools: https://github.com/cocaine/cocaine-tools
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
* Provided with `cocaine-tools <https://github.com/cocaine/cocaine-tools>`_ and embedded cocaine proxy
* PyPy support


Quick example
-------------------
Here's some extremely useful Cocaine app written in Python::

    #!/usr/bin/env python

    from cocaine.worker import Worker
    from cocaine.logging import Logger

    log = Logger()

    def echo(request, response):
        message = yield request.read()
        log.debug('Message received: \'{0}\'. Sending it back ...'.format(message))
        response.write(message)
        response.close()


    W = Worker()
    W.run({
        'ping': echo,
    })