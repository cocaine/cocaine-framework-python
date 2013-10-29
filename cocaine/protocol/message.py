#
#    Copyright (c) 2011-2013 Anton Tyurin <noxiouz@yandex.ru>
#    Copyright (c) 2011-2013 Other contributors as noted in the AUTHORS file.
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


class RPC:
    PROTOCOL_LIST = (
        HANDSHAKE,
        HEARTBEAT,
        TERMINATE,
        INVOKE,
        CHUNK,
        ERROR,
        CHOKE) = range(7)


PROTOCOL = {
    RPC.HANDSHAKE: {
        "id": RPC.HANDSHAKE,
        "tuple_type": ("uuid",)
    },
    RPC.HEARTBEAT: {
        "id": RPC.HEARTBEAT,
        "tuple_type": ()
    },
    RPC.TERMINATE: {
        "id": RPC.TERMINATE,
        "tuple_type": ("errno", "reason")
    },
    RPC.INVOKE: {
        "id": RPC.INVOKE,
        "tuple_type": ("event",)
    },
    RPC.CHUNK: {
        "id": RPC.CHUNK,
        "tuple_type": ("data",)
    },
    RPC.ERROR: {
        "id": RPC.ERROR,
        "tuple_type": ("errno", "reason")
    },
    RPC.CHOKE: {
        "id": RPC.CHOKE,
        "tuple_type": ()
    }
}


def closure(m_id, m_session, args):
    def wrapper():
        return m_id, m_session, args
    return wrapper


class BaseMessage(object):
    def __init__(self, protocol, id_, session, *args):
        prototype = protocol[id_]
        self.id = prototype['id']
        self.session = session
        for attr, value in zip(prototype['tuple_type'], args):
            setattr(self, attr, value)

        setattr(self, 'pack', closure(self.id, session, args))


class Message(BaseMessage):
    def __init__(self, id_, session, *args):
        super(Message, self).__init__(PROTOCOL, id_, session, *args)

    @staticmethod
    def initialize(data):
        id_, session, args = data
        return Message(RPC.PROTOCOL_LIST[id_], session, *args)
