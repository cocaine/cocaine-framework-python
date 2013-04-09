#! /usr/bin/env python

from pprint import pprint
from optparse import OptionParser
import sys
import errno

from cocaine.service.services import Service

DESCRIPTION=""
USAGE="USAGE: %prog [options]"
DEFAULT_PORT=10053
DEFAULT_HOST="localhost"


def main(hostname, port):
    node = Service("node", hostname, port)
    pprint(node.perform_sync("info"))


if __name__ == "__main__":
    parser = OptionParser(usage=USAGE, description=DESCRIPTION)
    parser.add_option("--port", type = "int", default=DEFAULT_PORT, help="Port number")
    parser.add_option("--host", type = "str", default=DEFAULT_HOST, help="Hostname")
    (options, args) = parser.parse_args()
    try:
        main(options.host, options.port)
    except Exception as err:
        if err.args[0] == errno.ECONNREFUSED:
            print "Invalid endpoint: %s:%d" % (options.host, options.port)
