# encoding: utf-8

import types
import io
import msgpack


class SimpleTimer(object):
    def __init__(self, processor = None):
        if processor is not None:
            assert(callable(processor))
            self.process = processor

    def __call__(self):
        try:
            self.result = self.process()
        except AttributeError:
            raise NotImplementedError("You have to implement the process() method")

        if self.result is None:
            return

        try:
            return [msgpack.packs(self.result)]
        except TypeError:
            self.result = iter(self.result)
            return self

    def __iter__(self):
        while True:
            yield msgpack.packs(next(self.result)) 


class SimpleServer(object):
    def __init__(self, processor = None):
        if processor is not None:
            assert(callable(processor))
            self.process = processor

    def __call__(self, request):
        request = msgpack.unpack(io.BytesIO(request))

        try:
            self.result = self.process(request)
        except AttributeError:
            raise NotImplementedError("You have to implement the process() method")

        if self.result is None:
            return

        try:
            return [msgpack.packs(self.result)]
        except TypeError:
            self.result = iter(self.result)
            return self

    def __iter__(self):
        while True:
            yield msgpack.packs(next(self.result)) 

