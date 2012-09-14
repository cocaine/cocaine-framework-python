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

#ifndef COCAINE_DEALER_PYTHON_BINDINGS_RESPONSE_HPP
#define COCAINE_DEALER_PYTHON_BINDINGS_RESPONSE_HPP

// NOTE: These are being redefined in Python.h
#undef _POSIX_C_SOURCE
#undef _XOPEN_SOURCE

#include "Python.h"

#include <boost/shared_ptr.hpp>

extern PyTypeObject response_wrapper_type;

namespace cocaine {
namespace dealer {

class response_t;

class response_holder_t {
    public:
        explicit response_holder_t(const boost::shared_ptr<response_t>& response_):
            m_response(response_)
        { }

        response_t* operator -> () {
            return m_response.get();
        }

    private:
        boost::shared_ptr<response_t> m_response;
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

} // namespace cocaine
} // namespace dealer

#endif
