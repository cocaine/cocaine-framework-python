#!/usr/bin/env python

import logging
import os
import sys

from cocaine.decorators.wsgi import django
from cocaine.logging import LoggerHandler
from cocaine.worker import Worker

__author__ = 'Evgeny Safronov <division494@gmail.com>'


log = logging.getLogger(__name__)
cocaineHandler = LoggerHandler()
log.addHandler(cocaineHandler)

dn = os.path.dirname
PROJECT_ROOT = os.path.abspath(dn(__file__))
DJANGO_PROJECT_ROOT = os.path.join(PROJECT_ROOT, 'enterprise')
sys.path.append(DJANGO_PROJECT_ROOT)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "enterprise.settings")


worker = Worker()
worker.run({
    'work':  django()
})
