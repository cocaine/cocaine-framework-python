#!/usr/bin/env python
from __future__ import print_function, unicode_literals

from cocaine.worker import Worker
from cocaine.decorators import wsgi

from app import app

print("A")
w = Worker()
print("B")
w.run({"http": wsgi(app)})
