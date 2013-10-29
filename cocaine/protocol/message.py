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
    def _wrapper():
        return m_id, m_session, args
    return _wrapper


class BaseMessage(type):
    def __call__(cls, id_, session, *tuple_types):
        prototype = PROTOCOL[id_]
        msg = object.__new__(cls)
        msg.__init__()
        setattr(msg, "id", prototype["id"])
        setattr(msg, "session", session)
        for attr, value in zip(prototype["tuple_type"], tuple_types):
            setattr(msg, attr, value)
        setattr(msg, "pack", closure(msg.id, msg.session, tuple_types))
        return msg


class Message(object):
    __metaclass__ = BaseMessage

    @staticmethod
    def initialize(data):
        id_, session, args = data
        return Message(RPC.PROTOCOL_LIST[id_], session, *args)
