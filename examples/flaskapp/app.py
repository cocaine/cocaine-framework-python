#!/usr/bin/env python


from flask import Flask

app = Flask(__name__)


@app.route('/ping')
def ping():
    return "PONG"


if __name__ == '__main__':
    app.run(debug=True)
