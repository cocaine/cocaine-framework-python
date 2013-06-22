#!/usr/bin/env python

from cocaine.services import Service
s = Service("node", "cocaine-log01g.kit.yandex.net")
for i in xrange(0,1000):
    s.info()
    s.reconnect()
    s.info()
