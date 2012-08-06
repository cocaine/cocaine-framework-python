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

#include <cocaine/dealer/response.hpp>
#include <cocaine/dealer/utils/error.hpp>

#include <cocaine/helpers/track.hpp>

#include "gil.hpp"
#include "response.hpp"

using namespace cocaine::dealer;

typedef cocaine::helpers::track_t<PyObject*, Py_DecRef> tracked_object_t;

PyObject* response_wrapper_t::construct(PyTypeObject * type, PyObject * args, PyObject * kwargs) {
    response_wrapper_t * self = reinterpret_cast<response_wrapper_t*>(type->tp_alloc(type, 0));

    if(self) {
        self->m_response = NULL;
    }

    return reinterpret_cast<PyObject*>(self);
}

int response_wrapper_t::initialize(response_wrapper_t * self, PyObject * args, PyObject * kwargs) {
    PyObject * response = NULL;

    if(!PyArg_ParseTuple(args, "O", &response)) {
        return -1;
    }

    if(!PyCObject_Check(response)) {
        PyErr_SetString(
            PyExc_TypeError,
            "Response objects cannot be instantiated directly"
        );

        return -1;
    }

    self->m_response = static_cast<response_holder_t*>(PyCObject_AsVoidPtr(response));

    BOOST_ASSERT(self->m_response);

    return 0;
}


void response_wrapper_t::destruct(response_wrapper_t * self) {
    if(self->m_response) {
        delete self->m_response;
    }

    self->ob_type->tp_free(self);
}

PyObject* response_wrapper_t::get(response_wrapper_t * self, PyObject * args, PyObject * kwargs) {
    static char timeout_keyword[] = "timeout";

    static char * keywords[] = {
        timeout_keyword, 
        NULL
    };

    double timeout = -1.0f;

    if(!PyArg_ParseTupleAndKeywords(args, kwargs, "|d:get", keywords, &timeout)) {
        return NULL;
    };

    bool success = false;
    chunk_data chunk;

    try {
        allow_threads_t allow_threads;
        success = (*self->m_response)->get(chunk, timeout);
    } catch(const dealer_error& e) {
        PyErr_SetString(
            PyExc_RuntimeError,
            e.what()
        );

        return NULL;
    } catch(const internal_error& e) {
        PyErr_SetString(
            PyExc_RuntimeError,
            e.what()
        );

        return NULL;
    }

    if(success) {
        return PyBytes_FromStringAndSize(
            static_cast<const char*>(chunk.data()),
            chunk.size()
        );
    } else {
        return PyBytes_FromString("");
    }
}

PyObject* response_wrapper_t::next(response_wrapper_t * self) {
    tracked_object_t args(Py_BuildValue("(d)", -1.0f));
    tracked_object_t result(response_wrapper_t::get(self, args, NULL));

    if(result.valid() && PyBytes_Size(result) == 0) {
        PyErr_SetNone(PyExc_StopIteration);
        return NULL;
    }

    return result.release();
}
