from cocaine.service.services import _BaseService

from cocaine.asio.message import PROTOCOL_LIST
from cocaine.asio.message import Message

class Urlfetcher(_BaseService):
    """ Port 12502
    [0, 256, [["http://company.yandex.ru", [], True]]]
    [0, 257, [["http://google.com", [], True]]]
    """

    def __init__(self):
        """ _counter - unique id generator
        _subscribers - mapping ids to callback
        """
        super(Urlfetcher, self).__init__(('localhost', 12502))
        self._subscribers = dict()
        self._counter = 0

    def _fetch(self, url, counter):
        self.m_w_stream.write([0, counter, [[url, [], True]]])

    def get(self, url):
        def wrapper(clbk):
            self._counter += 1
            self._subscribers[self._counter] = clbk
            self._fetch(url, self._counter)
        return wrapper

    def on_message(self, args):
        msg = Message.initialize(args)
        if msg is None:
            print "Drop invalid message"
            return
        if msg.id == PROTOCOL_LIST.index("rpc::chunk"):
            self._subscribers[msg.session](msg.data)
        elif msg.id == PROTOCOL_LIST.index("rpc::choke"):
            self._subscribers.pop(msg.session, None)
