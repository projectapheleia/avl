# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html
import os
import sys
from unittest import mock

MOCK_MODULES = [
    "cocotb", "cocotb.utils", "cocotb.simulator", "cocotb.triggers", "cocotb.clock", "cocotb.simtime",
    "cocotb.handle", "cocotb.binary", "cocotb.decorators", "cocotb.result", "cocotb.regression"
]
for mod_name in MOCK_MODULES:
    sys.modules[mod_name] = mock.MagicMock()

sys.path.insert(0, os.path.abspath('../../avl'))

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'avl'
copyright = '2025, apheleia'
author = 'apheleia'
release = '0.1'

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.napoleon',
    'sphinx.ext.viewcode',
    'sphinx.ext.graphviz',
    'sphinx.ext.inheritance_diagram',
    'sphinx.ext.autosummary'
]

templates_path = ['_templates']
exclude_patterns = []

# Internal attributes that configure how a class behaves - widths, masks,
# formats, the shared empty defaults - are documented and belong in the API
# reference. They are named explicitly so that the rest of the private members
# stay out of the built documentation.
_documented_private_members = [
    '_bits_dtype_',
    '_bits_format_',
    '_constraints_',
    '_current',
    '_default_fmt_',
    '_empty',
    '_events_',
    '_field_attributes_',
    '_file_',
    '_first',
    '_fixed_width_',
    '_flush_level',
    '_id_',
    '_idx_',
    '_line_',
    '_logdata',
    '_logfile',
    '_loggers',
    '_mask_',
    '_max_',
    '_phases',
    '_rand_',
    '_table_fmt_',
    '_table_recurse_',
    '_table_transpose_',
    '_value_dtype_',
    '_varname_',
]

autodoc_default_options = {
    'members': True,
    'member-order': 'bysource',
    'special-members': '__init__',
    'private-members': ','.join(_documented_private_members),
    'undoc-members': True,
    'exclude-members': '__weakref__'
}

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

graphviz_output_format = 'svg'
html_theme = 'sphinx_rtd_theme'

# -- Options for LaTeX (PDF) output -------------------------------------------
latex_elements = {
    # Paper size
    'papersize': 'a4paper',

    # Font size
    'pointsize': '11pt',

    # Additional LaTeX preamble
    'preamble': r'''
\usepackage{amsmath}
\usepackage{amssymb}
''',

    # Figure alignment
    'figure_align': 'H',
}

# Name of the master document
master_doc = 'index'
