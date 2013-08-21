from django.shortcuts import render

from cocaine.asio.service import Service


def apps(request):
    node = Service('node')
    list = node.list().get()
    return render(request, 'list.html', {
        'apps': list
    })
