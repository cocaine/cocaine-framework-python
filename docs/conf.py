# -*- coding: utf-8 -*-
from __future__ import print_function, unicode_literals

import os
import sys

print(os.getcwd())

sys.path.insert(0, '..')


extensions = ['sphinx.ext.autodoc', 'sphinx.ext.doctest']

source_suffix = '.rst'
master_doc = 'index'

# General information about the project.
project = 'cocaine-framework-python'
copyright = '2013, Evgeny Safronov <division494@gmail.com>'
version = '0.12.0'
release = '0'

exclude_trees = ['_build']
exclude_patterns = []
pygments_style = 'sphinx'


html_theme = 'default'
html_title = "%s v%s" % (project, version)
