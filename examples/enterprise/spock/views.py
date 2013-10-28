import json
from django.http import HttpResponse
from django.shortcuts import render
from cocaine.tools.actions import common
from cocaine.services import Service


locator = Locator()
locator.connect('localhost', 10053, 1.0, blocking=True)
node = Service('node')


def apps(request):
    node = Service('node')
    list_ = yield node.list()
    yield render(request, 'list.html', {
        'apps': list_
    })


def info(request):
    info = yield common.NodeInfo(node, locator).execute()
    yield HttpResponse(json.dumps(info))