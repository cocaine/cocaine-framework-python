#!/usr/bin/env python
#
#    Copyright (c) 2011-2012 Andrey Sibiryov <me@kobology.ru>
#    Copyright (c) 2012+ Anton Tyurin <noxiouz@yandex.ru>
#    Copyright (c) 2013+ Evgeny Safronov <division494@gmail.com>
#    Copyright (c) 2011+ Other contributors as noted in the AUTHORS file.
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

from setuptools import setup

setup(
    name="cocaine",
    version="0.12.6.0",
    author="Anton Tyurin",
    author_email="noxiouz@yandex.ru",
    maintainer='Evgeny Safronov',
    maintainer_email='division494@gmail.com',
    url="https://github.com/cocaine/cocaine-framework-python",
    description="Cocaine Python Framework for Cocaine Application Cloud.",
    long_description="A simple framework to ease the development of Cocaine apps",
    license="LGPLv3+",
    platforms=["Linux", "BSD", "MacOS"],
    namespace_packages=['cocaine'],
    include_package_data=True,
    zip_safe=False,
    packages=[
        "cocaine",
        "cocaine.common",
        "cocaine.decorators",
        "cocaine.detail",
        "cocaine.exceptions",
        "cocaine.services",
        "cocaine.worker",
    ],
    install_requires=open('./requirements.txt').read(),
    tests_require=open('./tests/requirements.txt').read(),
    test_suite='nose.collector',
    classifiers=[
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        # 'Programming Language :: Python :: 3.2',
        # 'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        "Programming Language :: Python :: Implementation :: PyPy",
        "Programming Language :: Python :: Implementation :: CPython",
        # 'Development Status :: 1 - Planning',
        # 'Development Status :: 2 - Pre-Alpha',
        # 'Development Status :: 3 - Alpha',
        'Development Status :: 4 - Beta',
        # 'Development Status :: 5 - Production/Stable',
        # 'Development Status :: 6 - Mature',
        # 'Development Status :: 7 - Inactive',
    ],
)
