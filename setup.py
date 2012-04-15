#!/usr/bin/env python
# encoding: utf-8

from distutils.core import setup, Extension

setup(
    name = "cocaine",
    version = "0.7.2-2",
    description = "Cocaine Python Framework",
    long_description = "A simple framework to ease the development of Cocaine apps",
    url = "https://github.com/kobolog/cocaine",
    author = "Andrey Sibiryov",
    author_email = "me@kobology.ru",
    license = "BSD 2-Clause",
    platforms = ["Linux", "BSD", "MacOS"],
    packages = ["cocaine", "cocaine.context", "cocaine.client", "cocaine.decorators"],
    ext_modules = [Extension("cocaine._client",
                             ["src/module.cpp", "src/client.cpp", "src/response.cpp"],
                             include_dirs = ["include"],
                             libraries = ["cocaine-dealer"])
    ],
    requires = ["msgpack"]
)
