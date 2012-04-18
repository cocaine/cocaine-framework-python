# encoding: utf-8

from functools import wraps

__all__ = ["timer"]

def timer(function):
    @wraps(function)
    def wrapper(io):
        function()

    return wrapper

