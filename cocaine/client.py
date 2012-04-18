# coding: utf-8

import types
import msgpack

from _client import Client as ClientBase

class Client(ClientBase):
    """
    Cocaine cloud balancer and scheduler.

    To create a new client instance, specify the location of the client
    configuration file.
    """
    
    def __init__(self, config):
        super(Client, self).__init__(config)

    def send(self, path, message):
        """
        Sends a ``message`` to the cloud using the specified ``path``.

        Valid ``path`` is a 'service/method'-like string, where 'service'
        is a configured service alias, and 'handle' is the actual app method
        name.

        If the ``message`` supports buffer protocol, it will be sent as-is,
        otherwise an attempt will be made to serialize it with MessagePack,
        sending the resulting bytestream instead.
        """

        try:
            service, handle = path.split('/')
        except ValueError:
            raise ValueError("Malformed message path")

        if not isinstance(message, types.StringTypes):
            message = msgpack.packb(message)

        return super(Client, self).send(service, handle, message)

    def get(self, path, message):
        """
        A simple wrapper around ``send``, which sends the ``message`` using
        the specified ``path``, waits for all the response chunks to arrive,
        stores them into a list and returns it to the user.
        """

        return [chunk for chunk in self.send(path, message)]
