/*
    Copyright (c) 2011-2012 Andrey Sibiryov <me@kobology.ru>
    Copyright (c) 2011-2012 Other contributors as noted in the AUTHORS file.

    This file is part of Cocaine.

    Cocaine is free software; you can redistribute it and/or modify
    it under the terms of the GNU Lesser General Public License as published by
    the Free Software Foundation; either version 3 of the License, or
    (at your option) any later version.

    Cocaine is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
    GNU Lesser General Public License for more details.

    You should have received a copy of the GNU Lesser General Public License
    along with this program. If not, see <http://www.gnu.org/licenses/>. 
*/

#include <cocaine/dealer/dealer.hpp>
#include <cocaine/dealer/utils/error.hpp>

#include <cocaine/helpers/track.hpp>

#include "gil.hpp"
#include "client.hpp"
#include "response.hpp"

using namespace cocaine::dealer;

typedef cocaine::helpers::track_t<PyObject*, Py_DecRef> tracked_object_t;

PyObject* client_object_t::construct(PyTypeObject * type, PyObject * args, PyObject * kwargs) {
    if(PyType_Ready(&response_wrapper_type) < 0) {
        return NULL;
    }

    client_object_t * self = reinterpret_cast<client_object_t*>(type->tp_alloc(type, 0));

    if(self) {
        self->m_client = NULL;
    }

    return reinterpret_cast<PyObject*>(self);
}

int client_object_t::initialize(client_object_t * self, PyObject * args, PyObject * kwargs) {
    static char config_keyword[] = "config";

    static char * keywords[] = {
        config_keyword, 
        NULL
    };

    const char * config = NULL;

    if(!PyArg_ParseTupleAndKeywords(args, kwargs, "s", keywords, &config)) {
        return -1;
    };

    try {
        self->m_client = new dealer_t(config);
    } catch(const internal_error& e) {
        PyErr_SetString(
            PyExc_RuntimeError,
            e.what()
        );

        return -1;
    }

    BOOST_ASSERT(self->m_client);

    return 0;
}

void client_object_t::destruct(client_object_t * self) {
    if(self->m_client) {
        delete self->m_client;
    }

    self->ob_type->tp_free(self);
}

PyObject* client_object_t::send(client_object_t * self, PyObject * args, PyObject * kwargs) {
    // base keywords
    static char service_keyword[]   = "service";
    static char handle_keyword[]    = "handle";
    static char message_keyword[]   = "message";

    // policy keywords
    static char urgent_keyword[]        = "urgent";
    static char deadline_keyword[]      = "deadline";
    static char timeout_keyword[]       = "timeout";
    static char max_retries_keyword[]   = "max_retries";

    static char * keywords[] = {
        service_keyword,
        handle_keyword,
        message_keyword,
        urgent_keyword,
        deadline_keyword,
        timeout_keyword,
        max_retries_keyword,
        NULL 
    };

    const char * service    = NULL;
    const char * handle     = NULL;
    const char * message    = NULL;

#ifdef PY_SSIZE_T_CLEAN
    Py_ssize_t size = 0;
#else
    int size = 0;
#endif

    int tmp_urgent;
    float tmp_deadline;
    float tmp_timeout;
    int tmp_max_retries;

    if(!PyArg_ParseTupleAndKeywords(args, kwargs, "ss|s#iffi:send", keywords,
                                    &service,
                                    &handle,
                                    &message,
                                    &size,
                                    &tmp_urgent,
                                    &tmp_deadline,
                                    &tmp_timeout,
                                    &tmp_max_retries)) {
        return NULL;
    }

    // get default policy for service
    message_policy_t policy = self->m_client->policy_for_service(service);

    // populate policy from kwargs
    if(!PyArg_ParseTupleAndKeywords(args, kwargs, "ss|s#iddi:send", keywords,
                                    &service,
                                    &handle,
                                    &message,
                                    &size,
                                    &policy.urgent,
                                    &policy.deadline,
                                    &policy.timeout,
                                    &policy.max_retries)) {
        return NULL;
    }

    response_holder_t * response = NULL;

    try {
        allow_threads_t allow_threads;
        response = new response_holder_t(
            self->m_client->send_message(
                message,
                size,
                message_path_t(service, handle),
                policy
            )
        );
    } catch(const dealer_error& e) {
        switch(e.code()) {
            case request_error:
                PyErr_SetString(
                    PyExc_ValueError,
                    e.what()
                );
                
                return NULL;

            case location_error:
                PyErr_SetString(
                    PyExc_LookupError,
                    e.what()
                );
                
                return NULL;

            default:
                PyErr_SetString(
                    PyExc_RuntimeError,
                    e.what()
                );

                return NULL;
        }
    } catch(const internal_error& e) {
        PyErr_SetString(
            PyExc_RuntimeError,
            e.what()
        );

        return NULL;
    }

    tracked_object_t ptr(PyCObject_FromVoidPtr(response, NULL)),
                     argpack(PyTuple_Pack(1, *ptr));

    PyObject * object = PyObject_Call(
        reinterpret_cast<PyObject*>(&response_wrapper_type),
        argpack,
        NULL
    );

    BOOST_ASSERT(object);

    return object;
}

