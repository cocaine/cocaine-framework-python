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

#ifndef COCAINE_DEALER_PYTHON_BINDING_COMMON_HPP
#define COCAINE_DEALER_PYTHON_BINDING_COMMON_HPP

// NOTE: These are being redefined in Python.h
#undef _POSIX_C_SOURCE
#undef _XOPEN_SOURCE

#include "Python.h"

namespace cocaine { namespace dealer {

class allow_threads_t {
public:
    allow_threads_t():
        m_thread(PyEval_SaveThread())
    { }

    ~allow_threads_t() {
        PyEval_RestoreThread(m_thread);
    }

private:
    PyThreadState * m_thread;
};

}}
#endif
