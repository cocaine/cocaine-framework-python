import json
import logging
import lockfile

from cocaine.proxy.proxy import CocaineProxy


log = logging.getLogger(__name__)


class Start(object):
    def __init__(self, port, cache, config, daemon, pidfile):
        self.port = port
        self.cache = cache
        self.config = config
        self.daemon = daemon
        self.pidfile = pidfile

    def execute(self):
        config = {}
        try:
            with open(self.config, 'r') as fh:
                config = json.loads(fh.read())
        except IOError as err:
            log.error(err)

        if self.daemon:
            import daemon
            context = daemon.DaemonContext(
                working_directory='.',
                pidfile=lockfile.FileLock('/var/run/cocaine-python-proxy.pid'),
            )
            with context:
                #todo: config from file or default
                formatter = logging.Formatter('[%(asctime)s] %(name)s: %(levelname)-8s: %(message)s')
                proxyLog = logging.getLogger('cocaine.proxy')
                handler = logging.FileHandler('/var/log/cocaine-python-proxy.log')
                handler.setFormatter(formatter)
                handler.setLevel(logging.DEBUG)
                proxyLog.addHandler(handler)
                proxyLog.setLevel(logging.DEBUG)

                proxy = CocaineProxy(self.port, self.cache, **config)
                proxy.run()
        else:
            proxy = CocaineProxy(self.port, self.cache, **config)
            proxy.run()