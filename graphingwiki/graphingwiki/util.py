# -*- coding: utf-8 -*-
"""
    Utils for graph generation, compatibility between MoinMoin versions
    etc.

    @copyright: 2006-2009 by Joachim Viide and
                             Juhani Eronen <exec@iki.fi>
    @license: MIT <http://www.opensource.org/licenses/mit-license.php>

    Permission is hereby granted, free of charge, to any person
    obtaining a copy of this software and associated documentation
    files (the "Software"), to deal in the Software without
    restriction, including without limitation the rights to use, copy,
    modify, merge, publish, distribute, sublicense, and/or sell copies
    of the Software, and to permit persons to whom the Software is
    furnished to do so, subject to the following conditions:

    The above copyright notice and this permission notice shall be
    included in all copies or substantial portions of the Software.

    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
    EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
    MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
    NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
    HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
    WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
    OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
    DEALINGS IN THE SOFTWARE.

"""

import re
import os
import StringIO
import cgi

from codecs import getencoder
from xml.dom.minidom import getDOMImplementation

from MoinMoin.action import cache
from MoinMoin.formatter.text_html import Formatter as HtmlFormatter
from MoinMoin import version as MoinVersion
from MoinMoin import caching
from MoinMoin import config
from MoinMoin import wikiutil
from MoinMoin.action import AttachFile
from MoinMoin.Page import Page
from MoinMoin.PageEditor import PageEditor
from MoinMoin.logfile import editlog

from graphingwiki import geoip_found, GeoIP, url_escape, id_escape, SEPARATOR
from graphingwiki.graph import Graph

MOIN_VERSION = float('.'.join(MoinVersion.release.split('.')[:2]))


import logging
log = logging.getLogger("graphingwiki")

# configure default logger as advised in logger docs
class NullHandler(logging.Handler):
    def emit(self, record):
        pass
log.addHandler(NullHandler())

# Some XML output helpers
def xml_document(top):
    # First, make the header
    impl = getDOMImplementation()
    xml = impl.createDocument(None, top, None)
    top = xml.documentElement

    return xml, top

def xml_node_id_and_text(doc, parent, nodename, text='', cdata='', **kw):
    node = doc.createElement(nodename)
    for key, value in kw.items():
        node.setAttribute(key, value)
    parent.appendChild(node)

    if text:
        text = doc.createTextNode(text)
        node.appendChild(text)
    # Does not work, I'm probably not using it correctly
    elif cdata:
        text = doc.createCDATASection(text)
        node.appendChild(text)

    return node

# Some GEOIP helpers
def geoip_init(request):
    _ = request.getText

    # Find GeoIP
    GEO_IP_PATH = getattr(request.cfg, 'gwiki_geoip_path', None)

    error = ''
    GEO_IP = None

    if not geoip_found:
        error = _("ERROR: GeoIP Python extensions not installed.")

    elif not GEO_IP_PATH:
        error = _("ERROR: GeoIP data file not found.")

    else:
        GEO_IP = GeoIP.open(GEO_IP_PATH, GeoIP.GEOIP_STANDARD)

    return GEO_IP, error

def geoip_get_coords(GEO_IP, text):
    if text is None:
        return None

    # Do not accept anything impossible
    if not re.match('^[a-zA-Z0-9.]+$', text):
        return None

    try:
        gir = GEO_IP.record_by_name(text)
    except:
        return None

    if not gir:
        return None

    return u"%s,%s" % (gir['longitude'], gir['latitude'])

# Methods related to Moin cache feature
def latest_edit(request):
    log = editlog.EditLog(request)
    entry = ''

    for x in log.reverse():
        entry = x
        break
    
    return entry.ed_time_usecs

def cache_exists(request, key):
    if getattr(request.cfg, 'gwiki_cache_invalidate', False):
        return False

    return cache.exists(request, key)

def cache_key(request, parts):
    data = StringIO.StringIO()

    # Make sure that repr of the object is unique
    for part in parts:
        data.write(repr(part))

    data = data.getvalue()

    return cache.key(request, content=data)

# Functions for starting and ending page
def enter_page(request, pagename, title):
    _ = request.getText

    request.emit_http_headers()

    title = _(title)
    request.theme.send_title(title,
                             pagename=pagename)
    # Start content - IMPORTANT - without content div, there is no
    # direction support!
    if not hasattr(request, 'formatter'):
        formatter = HtmlFormatter(request)
    else:
        formatter = request.formatter
    request.page.formatter = formatter

    request.write(request.page.formatter.startContent("content"))

def exit_page(request, pagename):
    # End content
    request.write(request.page.formatter.endContent()) # end content div
    # Footer
    request.theme.send_footer(pagename)
    request.theme.send_closing_html()

# Encoder from unicode to charset selected in config
encoder = getencoder(config.charset)
def encode(str):
    return encoder(str, 'replace')[0]

def form_escape(text):
    # Escape characters that break value fields in html forms
    #return re.sub('["]', lambda mo: '&#x%02x;' % ord(mo.group()), text)
    text = cgi.escape(text, quote=True)

    # http://bugs.python.org/issue9061
    text = text.replace("'", '&#x27;').replace('/', '&#x2F;')
    return text

def form_writer(fmt, *args):
    args = tuple(map(form_escape, args))
    return fmt % args

def url_parameters(args):
    req_url = u'?'

    url_args = list()
    for key in args:
        for val in args[key]:
            url_args.append(u'='.join(map(url_escape, [key, val])))

    req_url += u'&'.join(url_args)

    return req_url

def url_construct(request, args, name=''):
    if not name:
        name = request.page.page_name 

    req_url = request.getScriptname() + u'/' + name

    if args:
        req_url += url_parameters(args)

    return request.getQualifiedURL(req_url)

def make_tooltip(request, pagedata, format=''):
    _ = request.getText

    # Add tooltip, if applicable
    # Only add non-guaranteed attrs to tooltip
    pagemeta = dict()
    for key in pagedata.get('meta', dict()):
        pagemeta[key] = [x for x in pagedata['meta'][key]]
    for key in ['gwikicategory', '_notype']:
        if key in pagedata.get('out', dict()):
            pagemeta.setdefault(key, list()).extend(pagedata['out'][key])

    tooldata = str()
    if pagemeta:
        pagekeys = nonguaranteeds_p(pagemeta)
        tooldata = '\n'.join("-%s: %s" % 
                             (x == '_notype' and _('Links') or x,
                              ', '.join(pagemeta[x]))
                             for x in pagekeys)

    # Graphviz bug: too long tooltips make svg output fail
    if format in ['svg', 'zgr']:
        return tooldata[:6746]

    return tooldata

# Expand include arguments to a list of pages
def expand_include(request, pagename, args):
    pagelist = list()

    for inc_name in args:
        inc_name = wikiutil.AbsPageName(pagename, inc_name)
        if inc_name.startswith("^"):
            try:
                inc_match = re.compile(inc_name)
            except re.error:
                pass # treat as plain page name
            else:
                # Get user filtered readable page list
                pagelist.extend(request.rootpage.getPageList(
                        filter=inc_match.match))
        else:
            pagelist.append(inc_name)
        
    return pagelist
   
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

# FIXME: Is this needed?
def resolve_iw_url(request, wiki, page): 
    res = wikiutil.resolve_interwiki(request, wiki, page) 
    if res[3]:
        iw_url = './InterWiki' 
    else: 
        iw_url = res[1] + res[2] 
        
    return iw_url 

ATTACHMENT_SCHEMAS = ["attachment", "drawing"]

def encode_page(page):
    return encode(page)

def decode_page(page):
    return unicode(page, config.charset)


_url_re = None
def get_url_re():
    global _url_re
    if not _url_re:
        from MoinMoin.parser.text_moin_wiki import Parser
        # Ripped off from Parser
        url_pattern = u'|'.join(config.url_schemas)
        url_rule = ur'%(url_guard)s(%(url)s)\:([^\s\<%(punct)s]|([%(punct)s][^\s\<%(punct)s]))+' % {
            'url_guard': u'(^|(?<!\w))',
            'url': url_pattern,
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

        iw_list = wikiutil.load_wikimap(request)
        if iw_list.has_key(start):
            return 'interwiki'

    return 'page'

def filter_categories(request, candidates):
    # Let through only the candidates that are both valid category
    # names and WikiWords

    # Nah, the word rules in 1.6 were not for the feint for heart,
    # just use the wikiutil function until further notice

    return wikiutil.filterCategoryPages(request, candidates)

def get_url_ns(request, pagename, link):
    # Find out subpage level to adjust URL:s accordingly
    subrank = pagename.count('/')
    # Namespaced names
    if ':' in link:
        iw_list = wikiutil.load_wikimap(request)
        iwname = link.split(':')
        if iw_list.has_key(iwname[0]):
            return iw_list[iwname[0]] + iwname[1]
        else:
            return '../' * subrank + './InterWiki'
    # handle categories as ordernodes different
    # so that they would point to the corresponding categories
    if filter_categories(request, [link]):
        return '../' * subrank + './' + link
    else:
        return '../' * subrank + './%sProperty' % (link)

def format_wikitext(request, data):
    from MoinMoin.parser.text_moin_wiki import Parser

    request.page.formatter = request.formatter
    request.formatter.page = request.page
    parser = Parser(data, request)
    parser.request = request
    # No line anchors of any type to table cells
    request.page.formatter.in_p = 1
    parser._line_anchordef = lambda: ''

    # Do not parse macros from revision pages. For some reason,
    # it spawns multiple requests, which are not finished properly,
    # thus littering a number of readlocks. Besides, the macros do not
    # return anything useful anyway for pages they don't recognize
    if '?action=recall' in request.page.page_name:
        parser._macro_repl = lambda x: x

    # Using StringIO in order to strip the output
    data = StringIO.StringIO()
    request.redirect(data)
    # Produces output on a single table cell
    request.page.format(parser)
    request.redirect()

    return data.getvalue().strip()

def wrap_span(request, key, data, id):
    if not key:
        return format_wikitext(request, data)

    return '<span id="' + \
        id_escape('%(page)s%(sepa)s%(key)s%(sepa)s%(id)s' % 
                  {'page': request.page.page_name, 'sepa': SEPARATOR, 
                   'id': id, 'key': key}) + '">' + \
                   format_wikitext(request, data) + '</span>'

def absolute_attach_name(name, target):
    abs_method = target.split(':')[0]

    # Pages from MetaRevisions may have ?action=recall, breaking attach links
    if '?' in name:
        name = name.split('?', 1)[0]

    if abs_method in ATTACHMENT_SCHEMAS and not '/' in target:
        target = target.replace(':', ':%s/' % (name.replace(' ', '_')), 1)

    return target 

def get_selfname(request):
    if request.cfg.interwikiname:
        return request.cfg.interwikiname
    else:
        return 'Self'

def get_wikiurl(request):
    return request.getBaseURL() + '/'

def attachment_file(request, page, file):
    att_file = AttachFile.getFilename(request, page, file)
                                                   
    return att_file, os.path.isfile(att_file)

def attachment_url(request, page, file):
    att_url = AttachFile.getAttachUrl(page, file, request)
                                                   
    return att_url

# The load_ -functions try to minimise unnecessary reloading and overloading

def load_node(request, graph, node, urladd):
    load_origin = False

    nodeitem = graph.nodes.get(node)
    if not nodeitem:
        nodeitem = graph.nodes.add(node)
        load_origin = True

    # Get new data for current node
    adata = request.graphdata.load_graph(node, urladd, load_origin)

    if adata:
        nodeitem.update(adata.nodes.get(node))

    return adata

def load_children(request, graph, parent, urladd):
    adata = load_node(request, graph, parent, urladd)

    # If no data
    if not adata:
        return list()
    if not adata.nodes.get(parent):
        return list()

    children = set()

    # Add new nodes, edges that link to/from the current node
    for child in adata.edges.children(parent):
        if not graph.nodes.get(child):
            newnode = graph.nodes.add(child)
            newnode.update(adata.nodes.get(child))

        newedge = graph.edges.add(parent, child)
        edgedata = adata.edges.get(parent, child)
        newedge.update(edgedata)

        children.add(child)

    return children

def load_parents(request, graph, child, urladd):
    adata = load_node(request, graph, child, urladd)

    # If no data
    if not adata:
        return list()
    if not adata.nodes.get(child):
        return list()

    parents = set()

    # Add new nodes, edges that are the parents of the current node
    for parent in adata.edges.parents(child):
        if not graph.nodes.get(parent):
            newnode = graph.nodes.add(parent)
            newnode.update(adata.nodes.get(parent))

        newedge = graph.edges.add(parent, child)
        edgedata = adata.edges.get(parent, child)
        newedge.update(edgedata)

        parents.add(parent)

    return parents

def delete_moin_caches(request, pageitem):
    # Clear cache
    arena = PageEditor(request, pageitem.page_name)

    # delete pagelinks
    key = 'pagelinks'
    cache = caching.CacheEntry(request, arena, key, scope='item')
    cache.remove()

    # forget in-memory page text
    pageitem.set_raw_body(None)

    # clean the in memory acl cache
    pageitem.clean_acl_cache()

    request.graphdata.cache = dict()

    # clean the cache
    for formatter_name in request.cfg.caching_formats:
        key = formatter_name
        cache = caching.CacheEntry(request, arena, key, scope='item')
        cache.remove()

def template_regex(request, act=False):
    if act and hasattr(request.cfg.cache, 'page_template_regexact'):
        return request.cfg.cache.page_template_regexact

    if hasattr(request.cfg.cache, 'page_template_regex'):
        return request.cfg.cache.page_template_regex

    if MOIN_VERSION > 1.6:
        if not hasattr(request.cfg, 'page_template_regex'):
            request.cfg.page_template_regex = ur'(?P<all>(?P<key>\S+)Template)'
        if act:
            request.cfg.page_template_regexact = \
                re.compile(u'^%s$' % request.cfg.page_template_regex, 
                           re.UNICODE)
            return re.compile(request.cfg.page_template_regexact, re.UNICODE)
    else:
        # For editing.py unittests
        if not hasattr(request.cfg, 'page_template_regex'):
            request.cfg.page_template_regex = u'[a-z]Template$'

    return re.compile(request.cfg.page_template_regex, re.UNICODE)

def category_regex(request, act=False):
    if act and hasattr(request.cfg.cache, 'page_category_regexact'):
        return request.cfg.cache.page_category_regexact

    if hasattr(request.cfg.cache, 'page_category_regex'):
        return request.cfg.cache.page_category_regex

    if MOIN_VERSION > 1.6:
        if not hasattr(request.cfg, 'page_category_regex'):
            request.cfg.page_category_regex = \
                ur'(?P<all>Category(?P<key>(?!Template)\S+))'
        if act:
            request.cfg.page_category_regexact = \
                re.compile(u'^%s$' % request.cfg.page_category_regex, 
                           re.UNICODE)
            return re.compile(request.cfg.page_category_regexact, re.UNICODE)
    else:
        # For editing.py unittests
        if not hasattr(request.cfg, 'page_category_regex'):
            request.cfg.page_category_regex = u'^Category[A-Z]'

    return re.compile(request.cfg.page_category_regex, re.UNICODE)
