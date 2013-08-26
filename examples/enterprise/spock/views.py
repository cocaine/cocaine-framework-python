import json
from django.http import HttpResponse
from django.shortcuts import render

from cocaine.asio.service import Service, Locator
from cocaine.tools.actions import common

locator = Locator()
locator.connect('localhost', 10053, 1.0, blocking=True)
node = Service('node')


def apps(request):
    node = Service('node')
    list = yield node.list()
    yield render(request, 'list.html', {
        'apps': list
    })


def info(request):
    info = yield common.NodeInfo(node, locator).execute()
    yield HttpResponse(json.dumps(info))