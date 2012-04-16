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

#ifndef COCAINE_DEALER_PYTHON_BINDING_CLIENT_OBJECT
#define COCAINE_DEALER_PYTHON_BINDING_CLIENT_OBJECT

// NOTE: These are being redefined in Python.h
#undef _POSIX_C_SOURCE
#undef _XOPEN_SOURCE

#include "Python.h"

namespace cocaine { namespace dealer {

class client;

class client_object_t {
    public:
        PyObject_HEAD

        static PyObject* construct(PyTypeObject * type, PyObject * args, PyObject * kwargs);
        static int initialize(client_object_t * self, PyObject * args, PyObject * kwargs);
        static void destruct(client_object_t * self);

        static PyObject* send(client_object_t * self, PyObject * args, PyObject * kwargs);

    public:
        client * m_client;
};

static PyMethodDef client_object_methods[] = {
    { "send", (PyCFunction)client_object_t::send, METH_KEYWORDS,
        "Sends a message to the cloud." },
    { NULL, NULL, 0, NULL }
};

static PyTypeObject client_object_type = {
    PyObject_HEAD_INIT(&PyType_Type)
    0,                                          /* ob_size */
    "cocaine.client.Client",                    /* tp_name */
    sizeof(client_object_t),                    /* tp_basicsize */
    0,                                          /* tp_itemsize */
    (destructor)client_object_t::destruct,      /* tp_dealloc */
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
    "Client",                                   /* tp_doc */
    0,                                          /* tp_traverse */
    0,                                          /* tp_clear */
    0,                                          /* tp_richcompare */
    0,                                          /* tp_weaklistoffset */
    0,                                          /* tp_iter */
    0,                                          /* tp_iternext */
    client_object_methods,                      /* tp_methods */
    0,                                          /* tp_members */
    0,                                          /* tp_getset */
    0,                                          /* tp_base */
    0,                                          /* tp_dict */
    0,                                          /* tp_descr_get */
    0,                                          /* tp_descr_set */
    0,                                          /* tp_dictoffset */
    (initproc)client_object_t::initialize,      /* tp_init */
    0,                                          /* tp_alloc */
    client_object_t::construct                  /* tp_new */
};

}}
#endif
