# encoding: utf-8
#
#    Copyright (c) 2011-2012 Andrey Sibiryov <me@kobology.ru>
#    Copyright (c) 2011-2012 Other contributors as noted in the AUTHORS file.
#
#    This file is part of Cocaine.
#
#    Cocaine is free software; you can redistribute it and/or modify
#    it under the terms of the GNU Lesser General Public License as published by
#    the Free Software Foundation; either version 3 of the License, or
#    (at your option) any later version.
#
#    Cocaine is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#    GNU Lesser General Public License for more details.
#
#    You should have received a copy of the GNU Lesser General Public License
#    along with this program. If not, see <http://www.gnu.org/licenses/>. 
#

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

    def send(self, path, message = None, **kwargs):
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

        if message is not None:
            if not isinstance(message, types.StringTypes):
                message = msgpack.packb(message)

            return super(Client, self).send(service, handle, message, **kwargs)
        else:
            return super(Client, self).send(service, handle, **kwargs)

    def get(self, path, message = None, **kwargs):
        """
        A simple wrapper around ``send``, which sends the ``message`` using
        the specified ``path``, waits for all the response chunks to arrive,
        stores them into a list and returns it to the user.
        """

        return [chunk for chunk in self.send(path, message, **kwargs)]
