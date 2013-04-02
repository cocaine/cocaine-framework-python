__all__ = ["ServiceError", "RequestError"]

class CocaineError(Exception):
    """ Base exception """
    pass

class RequestError(CocaineError):
    """Exception raised when u try to request chunks from closed request """

    def __init__(self, msg):
        self.msg = msg

    def __repr__(self):
        return "RequestError: %s" % self.msg

    def __str__(self):
        return "RequestError: %s" % self.msg

class ServiceError(CocaineError):
    """Exception raised when error message is received from service"""

    def __init__(self, servicename, msg, code):
        self.servicename = servicename
        self.msg = msg
        self.code = code

    def __repr__(self):
        return "ServiceException [%d] %s: %s" % (self.code, self.servicename, self.msg)

    def __str__(self):
        return "ServiceException [%d] %s: %s" % (self.code, self.servicename, self.msg)
