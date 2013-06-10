#!/usr/bin/env python
# encoding: utf-8
#
#    Copyright (c) 2011-2012 Andrey Sibiryov <me@kobology.ru>
#    Copyright (c) 2011-2012 Other contributors as noted in the AUTHORS file.
#
#    This file is part of Cocaine.
#
#    Cocaine is free software; you can redistribute it and/or modify
#    it under the terms of the GNU Lesser General Public License as published by
#    the Free Software Foundation; either version 3 of the License, or
#    (at your option) any later version.
#
#    Cocaine is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#    GNU Lesser General Public License for more details.
#
#    You should have received a copy of the GNU Lesser General Public License
#    along with this program. If not, see <http://www.gnu.org/licenses/>. 
#

import sys
import os
import re

from setuptools import setup

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
try:
    with open("%s/debian/changelog" % BASE_DIR, 'r') as f:
        _version = re.findall(r"\(([^)]*)\)", f.readline())[0]
        print("Find version %s in debian/changelog" % _version)
except Exception:
    _version = "0.10.5"

if "--without-tools" in sys.argv:
    tools_requires = []
    tools_data = []
    tools_packages = []
    sys.argv.remove("--without-tools")
else:
    tools_requires = ['opster >= 4.0']
    tools_packages = ["cocaine.tools", "cocaine.tools.helpers"]
    tools_data = [
                ('/usr/bin/', ["scripts/cocaine-tool"])
    ]
    if not 'DEB_BUILD_GNU_TYPE' in os.environ:
        tools_data.append(
                ('/etc/bash_completion.d/', ["scripts/bash_completion.d/cocaine-tool"])
        )


setup(
    name="cocaine",
    version=_version,
    description="Cocaine Python Framework and Tools for Cocaine Application Cloud",
    long_description="A simple framework to ease the development of Cocaine apps\
    and tools for deploying applications in the cloud",
    url="https://github.com/cocaine/cocaine-framework-python",
    author="Anton Tyurin",
    author_email="noxiouz@yandex.ru",
    license="LGPLv3+",
    platforms=["Linux", "BSD", "MacOS"],
    packages=[
        "cocaine",
        "cocaine.asio",
        "cocaine.decorators",
        "cocaine.services",
        "cocaine.futures",
        "cocaine.logging"
    ] + tools_packages,
    install_requires=["msgpack_python", "tornado"] + tools_requires,
    data_files=tools_data
)

