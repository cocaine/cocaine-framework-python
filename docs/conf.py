# -*- coding: utf-8 -*-
import os
import sys
sys.path.insert(0, os.path.abspath(".."))


extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.coverage",
    "sphinx.ext.doctest",
    "sphinx.ext.extlinks",
    "sphinx.ext.intersphinx",
    "sphinx.ext.viewcode",
]

source_suffix = '.rst'
master_doc = 'index'

# General information about the project.
project = u'cocaine-framework-python'
copyright = u'2016, Anton Tiurin <noxiouz@yandex.ru>'
version = '0.12.5'
release = '1'

exclude_trees = ['_build']
exclude_patterns = []
pygments_style = 'sphinx'


# html_theme = 'default'
# html_title = "%s v%s" % (project, version)
on_rtd = os.environ.get('READTHEDOCS', None) == 'True'

# On RTD we can't import sphinx_rtd_theme, but it will be applied by
# default anyway.  This block will use the same theme when building locally
# as on RTD.
if not on_rtd:
    import sphinx_rtd_theme
    html_theme = 'sphinx_rtd_theme'
    html_theme_path = [sphinx_rtd_theme.get_html_theme_path()]
