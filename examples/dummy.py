#!/usr/bin/env python
# For YaSubbotnik at 15.06.2013

from cocaine.server.worker import Worker

W = Worker() # Dispatcher object

def event_handler(request, response):
    req = yield request.read() # Read incoming data
    if "Hello!" in req:
        response.write("Hello, world!") # Send data chunk
    else:
        response.write("Please, say 'Hello' to me!")
    response.close()

W.run({"hello" : event_handler}) # Run event loop - ready to work!
