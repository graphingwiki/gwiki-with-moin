# -*- coding: utf-8 -*-
"""
    Utils for graph generation etc.

    @copyright: 2006-2016 by Joachim Viide and
                             Jussi Eronen <exec@iki.fi>
"""
import re

from codecs import getencoder

from MoinMoin import config
from MoinMoin.config import multiconfig
from MoinMoin import wikiutil

from MoinMoin.parser.text_moin_wiki import Parser

from MoinMoin.metadata.constants import SPECIAL_ATTRS, NONEDITABLE_ATTRS, \
    ATTACHMENT_SCHEMAS

import logging
log = logging.getLogger("MoinMoin.metadata")
# configure default logger as advised in logger docs
class NullHandler(logging.Handler):
    def emit(self, record):
        pass
log.addHandler(NullHandler())

nonguaranteeds_p = lambda node: filter(lambda y: y not in
                                       SPECIAL_ATTRS, dict(node))

editable_p = lambda node: filter(lambda y: y not in 
                                 NONEDITABLE_ATTRS and not '->' in y, node)

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

def category_regex(request, act=False):
    if hasattr(request.cfg.cache, 'page_category_regex'):
        return request.cfg.cache.page_category_regex

    default = multiconfig.DefaultConfig.page_category_regex
    if act:
        default = "^{}$".format(default)
    default = re.compile(default, re.UNICODE)
    request.cfg.cache.page_category_regex = default

    return default

def template_regex(request, act=False):
    if hasattr(request.cfg.cache, 'page_template_regex'):
        return request.cfg.cache.page_template_regex

    default = multiconfig.DefaultConfig.page_template_regex
    if act:
        default = "^{}$".format(default)
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

# Encoder from unicode to charset selected in config
encoder = getencoder(config.charset)
def encode(str):
    return encoder(str, 'replace')[0]

def encode_page(page):
    return encode(page)

def decode_page(page):
    return unicode(page, config.charset)

def url_escape(text):
    # Escape characters that break links in html values fields, 
    # macros and urls with parameters
    return re.sub('[\]"\?#&+]', lambda mo: '%%%02x' % ord(mo.group()), text)

def doctest_request(graphdata=dict(), mayRead=True, mayWrite=True):
    class Request(object):
        pass

    class Config(object):
        pass

    class Object(object):
        pass

    class Cache(object):
        pass

    class GraphData(dict):
        def getpage(self, page):
            return self.get(page, dict())
    
    request = Request()
    request.cfg = Config()
    request.cfg.cache = Cache()
    request.cfg.cache.page_category_regex = category_regex(request)
    request.cfg.cache.page_category_regexact = category_regex(request, act=True)
    request.graphdata = GraphData(graphdata)

    request.user = Object()
    request.user.may = Object()
    request.user.may.read = lambda x: mayRead
    request.user.may.write = lambda x: mayWrite

    return request

def do_doctest():
    import doctest
    doctest.testmod()
