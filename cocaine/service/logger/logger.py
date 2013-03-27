from cocaine.service.services import _BaseService
from log_message import PROTOCOL_LIST
from log_message import Message


class Log(_BaseService):

    def __init__(self):
        super(Log, self).__init__(('localhost', 12501))
        self.m_target = "app/%s" % self.m_app_name
        self._counter = 0;

    def debug(self, data):
        self._counter += 1
        self.m_w_stream.write(Message("Message", 4, self._counter, self.m_target, data).pack())

    def info(self, data):
        self._counter += 1
        self.m_w_stream.write(Message("Message", 3, self._counter, self.m_target, data).pack())

    def warn(self, data):
        self._counter += 1
        self.m_w_stream.write(Message("Message", 2, self._counter, self.m_target, data).pack())

    def error(self, data):
        self._counter += 1
        self.m_w_stream.write(Message("Message", 1, self._counter, self.m_target, data).pack())
