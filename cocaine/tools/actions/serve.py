import json
import logging
from cocaine.futures import chain
from cocaine.proxy import Daemon
from cocaine.proxy.proxy import CocaineProxy

__author__ = 'Evgeny Safronov <division494@gmail.com>'


log = logging.getLogger(__name__)


class Start(object):
    def __init__(self, port, cache, config, daemon, pidfile, user):
        self.port = port
        self.cache = cache
        self.config = config
        self.daemon = daemon
        self.pidfile = pidfile
        self.user = user

    @chain.source
    def execute(self):
        config = {}
        try:
            with open(self.config, 'r') as fh:
                config = json.loads(fh.read())
        except IOError as err:
            log.error(err)

        proxy = CocaineProxy(self.port, self.cache, **config)
        if self.daemon:
            daemon = Daemon(self.pidfile, self.user)
            daemon.run = proxy.run
            daemon.start()
        else:
            proxy.run()