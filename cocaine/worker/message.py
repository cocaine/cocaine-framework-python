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

from cocaine.detail.util import msgpack_packb


class RPC(object):
    PROTOCOL_LIST = (
        HANDSHAKE,
        HEARTBEAT,
        TERMINATE,
        INVOKE,
        CHUNK,
        ERROR,
        CHOKE) = range(7)


class RPCv1(object):
    HANDSHAKE = 0
    HEARTBEAT = 0
    INVOKE = 0
    WRITE = 0
    ERROR = 1
    CLOSE = 2
    TERMINATE = 1


PROTOCOL = {
    RPC.HANDSHAKE: {
        'id': RPC.HANDSHAKE,
        'alias': 'Handshake',
        'tuple_type': ('uuid',)
    },
    RPC.HEARTBEAT: {
        'id': RPC.HEARTBEAT,
        'alias': 'Heartbeat',
        'tuple_type': ()
    },
    RPC.TERMINATE: {
        'id': RPC.TERMINATE,
        'alias': 'Terminate',
        'tuple_type': ('errno', 'reason')
    },
    RPC.INVOKE: {
        'id': RPC.INVOKE,
        'alias': 'Invoke',
        'tuple_type': ('event',)
    },
    RPC.CHUNK: {
        'id': RPC.CHUNK,
        'alias': 'Chunk',
        'tuple_type': ('data',)
    },
    RPC.ERROR: {
        'id': RPC.ERROR,
        'alias': 'Error',
        'tuple_type': ('errno', 'reason')
    },
    RPC.CHOKE: {
        'id': RPC.CHOKE,
        'alias': 'Choke',
        'tuple_type': ()
    }
}


def packv1(msg_id, session, *args):
    return msgpack_packb([msg_id, session, args])


def _make_packable(m_id, m_session, args):
    def wrapper():
        return msgpack_packb([m_session, m_id, args])
    return wrapper


class BaseMessage(object):
    def __init__(self, protocol, id_, session, *args):
        prototype = protocol[id_]

        self.id = prototype['id']
        self.session = session
        self.args = args

        self.__class__.__name__ = prototype['alias']
        for attr, value in zip(prototype['tuple_type'], args):
            setattr(self, attr, value)

        setattr(self, 'pack', _make_packable(self.id, session, args))

    def __str__(self):
        return '{0}({1}, {2}, {3})'.format(self.__class__.__name__, self.id, self.session, self.args)


class Message(BaseMessage):
    def __init__(self, id_, session, *args):
        super(Message, self).__init__(PROTOCOL, id_, session, *args)

    @staticmethod
    def initialize(data):
        session, id_, args = data
        return Message(RPC.PROTOCOL_LIST[id_], session, *args)
