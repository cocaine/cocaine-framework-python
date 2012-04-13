# encoding: utf-8

import types
import msgpack

class SimpleTimer(object):
    def __init__(self, processor = None):
        if processor is not None:
            assert(callable(processor))
            self.process = processor

    def __call__(self, io):
        try:
            response = self.process()
        except AttributeError:
            raise NotImplementedError("You have to implement the process() method")

        if isinstance(response, types.GeneratorType):
            [msgpack.pack(chunk, io) for chunk in response]
        elif response is not None:
            msgpack.pack(response, io)


class SimpleServer(object):
    def __init__(self, processor = None):
        if processor is not None:
            assert(callable(processor))
            self.process = processor

    def __call__(self, io):
        request = msgpack.unpack(io)['request']

        try:
            response = self.process(request)
        except AttributeError:
            raise NotImplementedError("You have to implement the process() method")

        if isinstance(response, types.GeneratorType):
            [msgpack.pack(chunk, io) for chunk in response]
        elif response is not None:
            msgpack.pack(response, io)

