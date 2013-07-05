# -*- coding: utf-8 -*-
import sys, os

extensions = ['sphinx.ext.autodoc', 'sphinx.ext.doctest']

templates_path = ['_templates']
source_suffix = '.rst'

# The master toctree document.
master_doc = 'index'

# General information about the project.
project = u'cocaine-framework-python'
copyright = u'2013, Evgeny Safronov <division494@gmail.com>'
version = '0.10.5'
release = '5'

exclude_patterns = []
pygments_style = 'sphinx'
html_theme = 'default'
html_static_path = ['_static']
htmlhelp_basename = 'cocaine-framework-pythondoc'


latex_elements = {
}

latex_documents = [
  ('index', 'cocaine-framework-python.tex', u'cocaine-framework-python Documentation',
   u'Evgeny Safronov \\textless{}division494@gmail.com\\textgreater{}', 'manual'),
]


man_pages = [
    ('index', 'cocaine-framework-python', u'cocaine-framework-python Documentation',
     [u'Evgeny Safronov <division494@gmail.com>'], 1)
]

texinfo_documents = [
  ('index', 'cocaine-framework-python', u'cocaine-framework-python Documentation',
   u'Evgeny Safronov <division494@gmail.com>', 'cocaine-framework-python', 'One line description of project.',
   'Miscellaneous'),
]