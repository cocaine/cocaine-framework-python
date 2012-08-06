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

#ifndef COCAINE_DEALER_PYTHON_BINDING_CLIENT_OBJECT
#define COCAINE_DEALER_PYTHON_BINDING_CLIENT_OBJECT

// NOTE: These are being redefined in Python.h
#undef _POSIX_C_SOURCE
#undef _XOPEN_SOURCE

#include "Python.h"

namespace cocaine { namespace dealer {

class dealer_t;

class client_object_t {
    public:
        PyObject_HEAD

        static PyObject* construct(PyTypeObject * type, PyObject * args, PyObject * kwargs);
        static int initialize(client_object_t * self, PyObject * args, PyObject * kwargs);
        static void destruct(client_object_t * self);

        static PyObject* send(client_object_t * self, PyObject * args, PyObject * kwargs);

    public:
        dealer_t * m_client;
};

extern PyTypeObject client_object_type;

}}

#endif
