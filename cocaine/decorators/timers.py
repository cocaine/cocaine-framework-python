# encoding: utf-8

from functools import wraps

def timer(function):
    @wraps(function)
    def wrapper(io):
        function()

    return wrapper

