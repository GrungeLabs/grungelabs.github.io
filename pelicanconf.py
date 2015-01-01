#!/usr/bin/env python
# -*- coding: utf-8 -*- #
from __future__ import unicode_literals

AUTHOR = u'Fahd Sultan'
SITENAME = u'Grunge Labs'
SITEURL = ''

PATH = 'content'

TIMEZONE = 'America/New_York'

GITHUB_URL = 'http://github.com/fsultan/'

#Style
THEME = "../pelican-themes/pelican-bootstrap3"
BOOTSTRAP_THEME = "superhero"
PYGMENTS_STYLE = "solarizeddark"
CUSTOM_CSS = 'static/custom.css'
BOOTSTRAP_NAVBAR_INVERSE = False

DEFAULT_LANG = u'en'

# Feed generation is usually not desired when developing
FEED_ALL_ATOM = None
CATEGORY_FEED_ATOM = None
TRANSLATION_FEED_ATOM = None
AUTHOR_FEED_ATOM = None
AUTHOR_FEED_RSS = None

DISPLAY_TAGS_ON_SIDEBAR = False
DISPLAY_CATEGORIES_ON_SIDEBAR = True
DISPLAY_RECENT_POSTS_ON_SIDEBAR = False

# Blogroll
LINKS = (('Pelican', 'http://getpelican.com/'),
         ('Python.org', 'http://python.org/'),
         ('Jinja2', 'http://jinja.pocoo.org/'),)

# Social widget
SOCIAL = ()

DEFAULT_PAGINATION = 10

# Uncomment following line if you want document-relative URLs when developing
#RELATIVE_URLS = True

#Article Info
SHOW_ARTICLE_AUTHOR = True
SHOW_ARTICLE_CATEGORY = True

# Tell Pelican to add 'extra/custom.css' to the output dir
STATIC_PATHS = ['images', 'extra/custom.css']

# Tell Pelican to change the path to 'static/custom.css' in the output dir
EXTRA_PATH_METADATA = {
    'extra/custom.css': {'path': 'static/custom.css'}
}
