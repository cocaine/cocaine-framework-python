# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, '..')

extensions = ['sphinx.ext.autodoc', 'sphinx.ext.doctest']

source_suffix = '.rst'
master_doc = 'index'

# General information about the project.
project = u'cocaine-framework-python'
copyright = u'2013, Evgeny Safronov <division494@gmail.com>'
version = '0.10.5'
release = '5'

exclude_trees = ['_build']
exclude_patterns = []
pygments_style = 'sphinx'


html_theme = 'default'
html_title = "%s v%s" % (project, version)