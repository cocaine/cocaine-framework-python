# encoding: utf-8
#
#    Copyright (c) 2011-2013 Anton Tyurin <noxiouz@yandex.ru>
#    Copyright (c) 2011-2013 Other contributors as noted in the AUTHORS file.
#
#    This file is part of Cocaine.
#
#    Cocaine is free software; you can redistribute it and/or modify
#    it under the terms of the GNU Lesser General Public License as published by
#    the Free Software Foundation; either version 3 of the License, or
#    (at your option) any later version.
#
#    Cocaine is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#    GNU Lesser General Public License for more details.
#
#    You should have received a copy of the GNU Lesser General Public License
#    along with this program. If not, see <http://www.gnu.org/licenses/>.
#

import functools
import logging
import os
import sys
import threading
import types

from tornado.wsgi import WSGIContainer

from cocaine.decorators.http import tornado
from cocaine.futures import chain
from cocaine.futures.chain import Chain


def start_response(func, status, response_headers, exc_info=None):
    if exc_info:
        try:
            raise (exc_info[0], exc_info[1], exc_info[2])
        finally:
            exc_info = None    # Avoid circular ref.

    return func.write_head(int(status.split(' ')[0]), response_headers)


def wsgi(application):
    @tornado
    def wrapper(request, response):
        req = yield request.read()
        for data in application(WSGIContainer.environ(req), functools.partial(start_response, response)):
            response.write(data)
        response.close()
    return wrapper


def django(root, settings, async=False, log=None):
    sys.path.append(root)
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', settings)

    if not async:
        from django.core.wsgi import get_wsgi_application
        return wsgi(get_wsgi_application())

    from django import http
    from django.core import signals
    from django.core.handlers import base
    from django.core.urlresolvers import set_script_prefix
    from django.core.handlers.wsgi import WSGIRequest, STATUS_CODE_TEXT
    from django.utils.encoding import force_str
    from django.conf import settings
    from django.core import exceptions
    from django.core import urlresolvers
    from django.views import debug

    if log is None:
        log = logging.getLogger(__name__)

    class WSGIHandler(base.BaseHandler):
        initLock = threading.Lock()
        request_class = WSGIRequest

        @chain.source
        def __call__(self, environ, start_response):
            if self._request_middleware is None:
                with self.initLock:
                    try:
                        if self._request_middleware is None:
                            self.load_middleware()
                    except:
                        self._request_middleware = None
                        raise

            set_script_prefix(base.get_script_name(environ))
            signals.request_started.send(sender=self.__class__)
            try:
                request = self.request_class(environ)
            except UnicodeDecodeError:
                log.warning('Bad Request (UnicodeDecodeError)', exc_info=sys.exc_info(), extra={'status_code': 400, })
                response = http.HttpResponseBadRequest()
            else:
                response = yield self.get_response(request)

            response._handler_class = self.__class__

            try:
                status_text = STATUS_CODE_TEXT[response.status_code]
            except KeyError:
                status_text = 'UNKNOWN STATUS CODE'
            status = '%s %s' % (response.status_code, status_text)
            response_headers = [(str(k), str(v)) for k, v in response.items()]
            for c in response.cookies.values():
                response_headers.append((str('Set-Cookie'), str(c.output(header=''))))
            start_response(force_str(status), response_headers)
            yield response

        @chain.source
        def get_response(self, request):
            try:
                urlconf = settings.ROOT_URLCONF
                urlresolvers.set_urlconf(urlconf)
                resolver = urlresolvers.RegexURLResolver(r'^/', urlconf)
                try:
                    response = None
                    for middleware_method in self._request_middleware:
                        response = middleware_method(request)
                        if response:
                            break

                    if response is None:
                        if hasattr(request, 'urlconf'):
                            urlconf = request.urlconf
                            urlresolvers.set_urlconf(urlconf)
                            resolver = urlresolvers.RegexURLResolver(r'^/', urlconf)

                        resolver_match = resolver.resolve(request.path_info)
                        callback, callback_args, callback_kwargs = resolver_match
                        request.resolver_match = resolver_match

                        for middleware_method in self._view_middleware:
                            response = middleware_method(request, callback, callback_args, callback_kwargs)
                            if response:
                                break

                    if response is None:
                        try:
                            response = yield Chain([lambda: callback(request, *callback_args, **callback_kwargs)])
                        except Exception as e:
                            for middleware_method in self._exception_middleware:
                                response = middleware_method(request, e)
                                if response:
                                    break
                            if response is None:
                                raise

                    if response is None:
                        if isinstance(callback, types.FunctionType):    # FBV
                            view_name = callback.__name__
                        else:                                           # CBV
                            view_name = callback.__class__.__name__ + '.__call__'
                        raise ValueError("The view %s.%s didn't return an HttpResponse object." % (callback.__module__,
                                                                                                   view_name))
                    if hasattr(response, 'render') and callable(response.render):
                        for middleware_method in self._template_response_middleware:
                            response = middleware_method(request, response)
                        response = response.render()

                except http.Http404 as e:
                    log.warning('Not Found: %s', request.path,
                                extra={
                                    'status_code': 404,
                                    'request': request
                                })
                    if settings.DEBUG:
                        response = debug.technical_404_response(request, e)
                    else:
                        try:
                            callback, param_dict = resolver.resolve404()
                            response = callback(request, **param_dict)
                        except:
                            signals.got_request_exception.send(sender=self.__class__, request=request)
                            response = self.handle_uncaught_exception(request, resolver, sys.exc_info())
                except exceptions.PermissionDenied:
                    log.warning(
                        'Forbidden (Permission denied): %s', request.path,
                        extra={
                            'status_code': 403,
                            'request': request
                        })
                    try:
                        callback, param_dict = resolver.resolve403()
                        response = callback(request, **param_dict)
                    except:
                        signals.got_request_exception.send(sender=self.__class__, request=request)
                        response = self.handle_uncaught_exception(request, resolver, sys.exc_info())
                except SystemExit:
                    raise
                except:
                    signals.got_request_exception.send(sender=self.__class__, request=request)
                    response = self.handle_uncaught_exception(request, resolver, sys.exc_info())
            finally:
                urlresolvers.set_urlconf(None)

            try:
                for middleware_method in self._response_middleware:
                    response = middleware_method(request, response)
                response = self.apply_response_fixes(request, response)
            except:
                signals.got_request_exception.send(sender=self.__class__, request=request)
                response = self.handle_uncaught_exception(request, resolver, sys.exc_info())

            yield response

    application = WSGIHandler()

    @tornado
    def wrapper(request, response):
        req = yield request.read()
        datas = yield application(WSGIContainer.environ(req), functools.partial(start_response, response))
        for data in datas:
            response.write(data)
        response.close()
    return wrapper
