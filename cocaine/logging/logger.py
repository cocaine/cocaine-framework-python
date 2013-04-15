import sys

from cocaine.services import Service
from log_message import PROTOCOL_LIST
from log_message import Message

__all__ = ["Logger"]

VERBOSITY_LEVELS = {
    0 : "ignore",
    1 : "error",
    2 : "warn",
    3 : "info",
    4 : "debug"
}

def _construct_logger_methods(cls, verbosity_level):
    def closure(_lvl):
        if _lvl <= verbosity_level:
            def func(data):
                cls._counter += 1
                cls._logger.w_stream.write(Message("Message", cls._counter, _lvl,  cls.target, str(data)).pack())
            return func
        else:
            def func(data):
                pass
            return func

    setattr(cls, "_counter", 0)
    for level, name in VERBOSITY_LEVELS.iteritems():
        setattr(cls, name, closure(level))

class _STDERR_Logger(object):

    def debug(self, data):
        print >> sys.stderr, data

    def info(self, data):
        print >> sys.stderr, data

    def warn(self, data):
        print >> sys.stderr, data

    def error(self, data):
        print >> sys.stderr, data

    def ignore(self, data):
        print >> sys.stderr, data


class Logger(object):

    def __new__(cls):
        if not hasattr(cls, "_instanse"):
            instanse = object.__new__(cls)
            try:
                _logger = Service("logging")
                verbosity = _logger.perform_sync("verbosity")
                setattr(instanse, "_logger", _logger)
                try:
                    setattr(instanse, "target", "app/%s" % sys.argv[sys.argv.index("--app") + 1])
                except ValueError: 
                    setattr(instanse, "target", "app/%s" % "standalone" )
                _construct_logger_methods(instanse, verbosity)
            except Exception as err:
                instanse = _STDERR_Logger()
                instanse.warn("Logger init error: %s. Use stderr logger" % err)
            cls._instanse = instanse
        return cls._instanse
