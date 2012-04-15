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

int response_object_t::constructor(response_object_t * self, PyObject * args, PyObject * kwargs) {
    return 0;
}


void response_object_t::destructor(response_object_t * self) {
    self->ob_type->tp_free(self);
}

PyObject* response_object_t::get(response_object_t * self, PyObject * args, PyObject * kwargs) {
    Py_RETURN_NONE;
}

PyObject* response_object_t::iter_next(response_object_t * it) {
    PyErr_SetString(
        PyExc_NotImplementedError,
        "Method is not yet implemented"
    );

    return NULL;
}
