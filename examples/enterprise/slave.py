#!/usr/bin/env python
import logging
import os

from cocaine.decorators.wsgi import django
from cocaine.logging import LoggerHandler
from cocaine.worker import Worker

__author__ = 'Evgeny Safronov <division494@gmail.com>'

PROJECT_NAME = 'enterprise'


log = logging.getLogger(__name__)
cocaineHandler = LoggerHandler()
log.addHandler(cocaineHandler)

PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))

worker = Worker()
worker.run({
    'work': django(**{
        'root': os.path.join(PROJECT_ROOT, PROJECT_NAME),
        'settings': '{0}.settings'.format(PROJECT_NAME),
        'async': True,
        'log': log
    })
})
