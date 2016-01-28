# -*- coding: utf-8 -*-
"""
    Utils for graph generation etc.

    @copyright: 2006-2016 by Joachim Viide and
                             Jussi Eronen <exec@iki.fi>
"""
import re

from MoinMoin import config
from MoinMoin import wikiutil
from MoinMoin import caching

from MoinMoin.parser.text_moin_wiki import Parser

import logging
log = logging.getLogger("MoinMoin.metadata")

# Default node attributes that should not be shown
SPECIAL_ATTRS = ["gwikilabel", "gwikisides", "gwikitooltip", "gwikiskew",
                 "gwikiorientation", "gwikifillcolor", 'gwikiperipheries',
                 'gwikishapefile', "gwikishape", "gwikistyle", 
                 'gwikicategory', 'gwikiURL', 'gwikiimage', 'gwikiinlinks',
                 'gwikicoordinates']
nonguaranteeds_p = lambda node: filter(lambda y: y not in
                                       SPECIAL_ATTRS, dict(node))

NONEDITABLE_ATTRS = ['gwikiinlinks', '-', 'gwikipagename']
editable_p = lambda node: filter(lambda y: y not in 
                                 NONEDITABLE_ATTRS and not '->' in y, node)

NO_TYPE = u'_notype'

# XXX replace by Parser's URL rule?
_url_re = None
def get_url_re():
    global _url_re
    if not _url_re:
        # Ripped off from Parser
        url_rule = ur'%(url_guard)s(%(url)s)\:([^\s\<%(punct)s]|([%(punct)s][^\s\<%(punct)s]))+' % {
            'url_guard': u'(^|(?<!\w))',
            'url': Parser.url_scheme,
            'punct': Parser.punct_pattern,
        }
        _url_re = re.compile(url_rule)
    return _url_re

def node_type(request, nodename):
    if ':' in nodename:
        if get_url_re().search(nodename):
            return 'url'

        start = nodename.split(':')[0]
        if start in ATTACHMENT_SCHEMAS:
            return 'attachment'

        # Check if we know of the wiki an interwiki-style link is
        # trying to refer to. If not, assume that this should not be a
        # link.
        iw_list = wikiutil.load_wikimap(request)
        if iw_list.has_key(start):
            return 'interwiki'
        elif start:
            return 'none'

    return 'page'

def category_regex(request):
    if hasattr(request.cfg.cache, 'page_category_regex'):
        return request.cfg.cache.page_category_regex

    default = config.multiconfig.DefaultConfig.page_category_regex
    default = re.compile(default, re.UNICODE)
    request.cfg.cache.page_category_regex = default

    return default

def template_regex(request):
    if hasattr(request.cfg.cache, 'page_template_regex'):
        return request.cfg.cache.page_template_regex

    default = config.multiconfig.DefaultConfig.page_template_regex
    default = re.compile(default, re.UNICODE)
    request.cfg.cache.page_template_regex = default

    return default

def filter_categories(request, candidates):
    # Let through only the candidates that are both valid category
    # names and WikiWords

    # Nah, the word rules in 1.6 were not for the feint for heart,
    # just use the wikiutil function until further notice
    # XXX
    return wikiutil.filterCategoryPages(request, candidates)

def encode_page(page):
    return encode(page)

def decode_page(page):
    return unicode(page, config.charset)
