#!/usr/bin/env python

from flask import Flask

from cocaine.services import SyncService

app = Flask(__name__)

NAMESPACE = "testnamespace"
KEY = "testkey"

storage = SyncService("storage")


@app.route('/')
def hello(name=None):
    return "HELLO!"


@app.route('/read')
def read():
    data = storage.run_sync(storage.read(NAMESPACE, KEY).rx.get(), timeout=1)
    return data

if __name__ == "__main__":
    app.run(debug=True)
