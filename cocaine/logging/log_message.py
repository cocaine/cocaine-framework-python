# encoding: utf-8
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

from itertools import izip

PROTOCOL_LIST = (
    "Message",
)

PROTOCOL = {
    "Message": {
        "id": PROTOCOL_LIST.index("Message"),
        "tuple_type": ("level", "appname", "content")
    }
}


def closure(m_id, session, args):
    def _wrapper():
        return m_id, session, args
    return _wrapper


class MessageInit(type):

    def __call__(cls, rpc_tag, session, *tuple_types):
        obj_dict = PROTOCOL[rpc_tag]
        msg = object.__new__(cls)
        msg.__init__()
        setattr(msg, "id", obj_dict["id"])
        setattr(msg, "session", session)
        [setattr(msg, attr, value) for attr, value in izip(obj_dict["tuple_type"], tuple_types)]
        setattr(msg, "pack", closure(msg.id, session, tuple_types))
        return msg


class Message(object):
    __metaclass__ = MessageInit

    @staticmethod
    def initialize(unpacked_data):
        try:
            _id = unpacked_data[0]
            session = unpacked_data[1]
            args = unpacked_data[2]  # if unpacked_data[1] is not None else list()
            return Message(PROTOCOL_LIST[_id], session, *args)
        except Exception:
            return None
