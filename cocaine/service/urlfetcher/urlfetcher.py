from cocaine.service.services import _BaseService

class Urlfetcher(_BaseService):

    def __init__(self):
        super(Urlfetcher, self).__init__(('localhost', 12502))
        self._subscribers = dict()
        self._counter = 0

    def _fetch(self, url, counter):
        self.m_w_stream.write([0, counter, [["http://company.yandex.ru", [], True]]])

    def get(self, url):
        def wrapper(clbk):
            self._counter += 1
            self._subscribers[self._counter] = clbk
            self._fetch(url, self._counter)
        return wrapper

    def on_message(self, *args):
        try:
            num =  args[0][1]
            data = args[0][2]
            self._subscribers[num](data)
            self._subscribers.pop(num, None)
        except Exception as err:
            print "ERROR", str(err)
