from __future__ import print_function

from cocaine.tools.actions import docker

__author__ = 'Evgeny Safronov <division494@gmail.com>'


client = docker.Client(url='http://localhost:4243', timeout=120.0)

print(client.info().get())
print(client.images().get())
client.build('/Users/esafronov/dock', tag='3hren/cocaine-test1:test-tag', quiet=True, streaming=print).get()
client.push('3hren/cocaine-test1', {
    'username': '3hren',
    'password': 'docker',
    'email': 'division494@gmail.com'
}, registry='localhost:5000', streaming=print).get()
print(client.containers().get())
