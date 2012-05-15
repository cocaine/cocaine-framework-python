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

#ifndef COCAINE_DEALER_PYTHON_BINDINGS_RESPONSE_HPP
#define COCAINE_DEALER_PYTHON_BINDINGS_RESPONSE_HPP

// NOTE: These are being redefined in Python.h
#undef _POSIX_C_SOURCE
#undef _XOPEN_SOURCE

#include "Python.h"

#include <boost/shared_ptr.hpp>

namespace cocaine { namespace dealer {

class response;

class response_holder_t {
    public:
        explicit response_holder_t(const boost::shared_ptr<response>& response_):
            m_response(response_)
        { }

        response* operator -> () {
            return m_response.get();
        }

    private:
        boost::shared_ptr<response> m_response;
};

class response_wrapper_t {
    public:
        PyObject_HEAD

        static PyObject* construct(PyTypeObject * type, PyObject * args, PyObject * kwargs);
        static int initialize(response_wrapper_t * self, PyObject * args, PyObject * kwargs);
        static void destruct(response_wrapper_t * self);

        static PyObject* get(response_wrapper_t* self, PyObject * args, PyObject * kwargs);
        static PyObject* next(response_wrapper_t * self);

    public:
        response_holder_t * m_response;
};

static PyMethodDef response_wrapper_methods[] = {
    { "get", (PyCFunction)response_wrapper_t::get, METH_KEYWORDS,
        "Waits for a next response chunk with an optional timeout." },
    { NULL, NULL, 0, NULL }
};

static PyTypeObject response_wrapper_type = {
    PyObject_HEAD_INIT(&PyType_Type)
    0,                                          /* ob_size */
    "cocaine.client.Response",                  /* tp_name */
    sizeof(response_wrapper_t),                 /* tp_basicsize */
    0,                                          /* tp_itemsize */
    (destructor)response_wrapper_t::destruct,   /* tp_dealloc */
    0,                                          /* tp_print */
    0,                                          /* tp_getattr */
    0,                                          /* tp_setattr */
    0,                                          /* tp_compare */
    0,                                          /* tp_repr */
    0,                                          /* tp_as_number */
    0,                                          /* tp_as_sequence */
    0,                                          /* tp_as_mapping */
    0,                                          /* tp_hash */
    0,                                          /* tp_call */
    0,                                          /* tp_str */
    0,                                          /* tp_getattro */
    0,                                          /* tp_setattro */
    0,                                          /* tp_as_buffer */
    Py_TPFLAGS_DEFAULT,                         /* tp_flags */
    "Deferred Response",                        /* tp_doc */
    0,                                          /* tp_traverse */
    0,                                          /* tp_clear */
    0,                                          /* tp_richcompare */
    0,                                          /* tp_weaklistoffset */
    PyObject_SelfIter,                          /* tp_iter */
    (iternextfunc)response_wrapper_t::next,     /* tp_iternext */
    response_wrapper_methods,                   /* tp_methods */
    0,                                          /* tp_members */
    0,                                          /* tp_getset */
    0,                                          /* tp_base */
    0,                                          /* tp_dict */
    0,                                          /* tp_descr_get */
    0,                                          /* tp_descr_set */
    0,                                          /* tp_dictoffset */
    (initproc)response_wrapper_t::initialize,   /* tp_init */
    0,                                          /* tp_alloc */
    response_wrapper_t::construct               /* tp_new */
};

}}
#endif
