import json
import time

from cocaine.services import Service

__author__ = 'Evgeny Safronov <division494@gmail.com>'


__doc__ = '''ELASTICSEARCH SERVICE USAGE EXAMPLE.
Elasticsearch must be started. Also elasticsearch cocaine plugin must be properly configured.
'''

now = time.strftime('%Y-%m-%dT%H:%M:%S', time.gmtime(time.time()))

elastic = Service('elasticsearch')

##### INDEX #####
print('Index simple message with index "/twitter/tweet/1"')
data = {
    'user': '3Hren',
    'post_date': now,
    'message': 'Hello, Elasticsearch!'
}
print('Result:', elastic.index(json.dumps(data), 'twitter', 'tweet', '1').get())
print('')

##### GET #####
print('And now get it')
print(elastic.get('twitter', 'tweet', '1').get())
print('')

##### INDEX GENERATE #####
print('Index simple message with id generated and get it')
data = {
    'user': '3Hren',
    'post_date': now,
    'message': 'Hello!'
}
status, index = elastic.index(json.dumps(data), 'twitter', 'tweet').get()
print([status, index])
print(elastic.get('twitter', 'tweet', '{0}'.format(index)).get())
print('')


##### SEARCH #####
print('Search records with message "Hello" from "/twitter/tweet"')
status, count, hits = elastic.search('twitter', 'tweet', 'message:Hello').get()
print(status, count, json.loads(hits))
print('')

print('Search 2 records with message "Hello" from "/twitter"')
status, count, hits = elastic.search('twitter', '', 'message:Hello', 2).get()
print(status, count, json.loads(hits))
print('')

##### DELETE #####
print('Do double delete record "/twitter/tweet/1" and get it')
print(elastic.delete('twitter', 'tweet', '1').get())
print(elastic.delete('twitter', 'tweet', '1').get())
print(elastic.get('twitter', 'tweet', '1').get())