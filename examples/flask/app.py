#!/usr/bin/env python

from flask import Flask

from cocaine.services import Service

app = Flask(__name__)

NAMESPACE = "testnamespace"
KEY = "testkey"

storage = Service("storage")


@app.route('/')
def hello(name=None):
    return "HELLO!"


@app.route('/read')
def read():
    data = storage.read(NAMESPACE, KEY).get()
    return data

if __name__ == "__main__":
    app.run(debug=True)
