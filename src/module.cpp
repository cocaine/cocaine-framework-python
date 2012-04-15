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

#include "objects.hpp"

using namespace cocaine::dealer;

extern "C" {

void init_client(void) {
    PyObject * module = Py_InitModule3(
        "cocaine._client",
        NULL,
        "Client Objects"
    );

    PyType_Ready(&client_object_type);
    PyType_Ready(&response_object_type);
    
    Py_INCREF(&client_object_type);

    PyModule_AddObject(
        module,
        "Client",
        reinterpret_cast<PyObject*>(&client_object_type)
    );
}

}

