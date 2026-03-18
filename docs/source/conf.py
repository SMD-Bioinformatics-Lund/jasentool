import datetime

project = 'Jasentool'
copyright = f'{datetime.date.today().year}, SMD Bioinformatics Lund'
author = 'SMD Bioinformatics Lund'

source_suffix = '.md'
master_doc = 'index'

extensions = [
    'sphinx_rtd_theme',
    'myst_parser',
]

html_theme = 'sphinx_rtd_theme'
html_static_path = ['_static']
html_css_files = ['custom.css']

exclude_patterns = ['_build']
