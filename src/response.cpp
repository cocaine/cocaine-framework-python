//
// Copyright (C) 2011-2012 Andrey Sibiryov <me@kobology.ru>
//
// Licensed under the BSD 2-Clause License (the "License");
// you may not use this file except in compliance with the License.
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.
//

#include <cocaine/dealer/response.hpp>

#include "response.hpp"

using namespace cocaine::dealer;

PyObject* response_object_t::constructor(PyTypeObject * type, PyObject * args, PyObject * kwargs) {
    response_object_t * self = reinterpret_cast<response_object_t*>(type->tp_alloc(type, 0));

    if(self) {
        self->m_future = NULL;
    }

    return reinterpret_cast<PyObject*>(self);
}

int response_object_t::initializer(response_object_t * self, PyObject * args, PyObject * kwargs) {
    PyObject * future = NULL;

    if(!PyArg_ParseTuple(args, "O", &future)) {
        return -1;
    }

    if(!PyCObject_Check(future)) {
        PyErr_SetString(
            PyExc_TypeError,
            "Response objects cannot be instantiated directly"
        );

        return -1;
    }

    self->m_future = static_cast<response_wrapper_t*>(PyCObject_AsVoidPtr(future));

    BOOST_ASSERT(self->m_future);

    return 0;
}


void response_object_t::destructor(response_object_t * self) {
    if(self->m_future) {
        delete self->m_future;
    }

    self->ob_type->tp_free(self);
}

PyObject* response_object_t::get(response_object_t * self, PyObject * args, PyObject * kwargs) {
    bool success = false;
    data_container chunk;

    try {
        Py_BEGIN_ALLOW_THREADS
            success = (*self->m_future)->get(&chunk);
        Py_END_ALLOW_THREADS

        if(success) {
            return PyBytes_FromStringAndSize(
                static_cast<const char*>(chunk.data()),
                chunk.size()
            );
        } else {
            return PyBytes_FromString("");
        }
    } catch(...) {
        PyErr_SetString(
            PyExc_RuntimeError,
            "Something went wrong"
        );

        return NULL;
    }
}

PyObject* response_object_t::iter_next(response_object_t * it) {
    PyErr_SetString(
        PyExc_NotImplementedError,
        "Method is not yet implemented"
    );

    return NULL;
}
