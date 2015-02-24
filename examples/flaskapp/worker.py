#!/usr/bin/env python

from cocaine.worker import Worker
from cocaine.decorators import wsgi

from app import app

print "A"
w = Worker()
print "B"
w.run({"http": wsgi(app)})
