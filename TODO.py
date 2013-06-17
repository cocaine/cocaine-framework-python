__author__ = 'EvgenySafronov <division494@gmail.com>'


#todo: Currently chain and stream implementation requires explicitly read CHOKE. Do it automatically
issue1 = '''
This leads to dirty code like this:
>>> crashlogs = yield self.storage.find('crashlogs', (self.name,))
>>> yield # get choke

OR

If service function is the first in chain there is no way to read it all. That leads to double invoking entire chain.
May be we should store fetched chunks in list and to send it when they are ALL arrived? Next code leads to the doubled
chain invocation:

>>> chain = self.node.info()
>>> chain.then(self.processResult).run()

processResult method will be invoked two times! With real node info chunk and with None
'''