# encoding: utf-8

import types
import msgpack

from functools import wraps

__all__ = ["zeromq", "native"]

def pack(response, io):
    if isinstance(response, types.StringTypes):
        io.write(response)
    elif isinstance(response, types.GeneratorType):
        [pack(chunk, io) for chunk in response]
    elif response is not None:
        msgpack.pack(response, io)

def zeromq(function):
    @wraps(function)
    def wrapper(io):
        pack(function(msgpack.unpack(io)), io)

    return wrapper

def native(function):
    @wraps(function)
    def wrapper(io):
        pack(function(**msgpack.unpack(io)), io)

    return wrapper

