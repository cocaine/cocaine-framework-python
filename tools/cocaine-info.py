#! /usr/bin/env python

from pprint import pprint
from optparse import OptionParser
import sys
import errno

from cocaine.service.services import Service

DESCRIPTION=""
USAGE="USAGE: %prog [options]"

parser = OptionParser(usage=USAGE, description=DESCRIPTION)
parser.add_option("--port", type = "int", default=10053, help="Port number")
parser.add_option("--host", type = "str", default="localhost", help="Hostname")

(options, args) = parser.parse_args()

def main(hostname=options.host, port=options.port):
    node = Service("node", hostname, port)
    pprint(node.perform_sync("info"))


if __name__ == "__main__":
    try:
        main()
    except Exception as err:
        if err.args[0] == errno.ECONNREFUSED:
            print "Invalid endpoint: %s:%d" % (options.host, options.port)
