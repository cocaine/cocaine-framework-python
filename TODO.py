__author__ = 'EvgenySafronov <division494@gmail.com>'


#todo: Currently chain and stream implementation requires explicitly read CHOKE. Do it automatically
issue1 = '''
This leads to dirty code like this:
>>> crashlogs = yield self.storage.find('crashlogs', (self.name,))
>>> yield # get choke
'''