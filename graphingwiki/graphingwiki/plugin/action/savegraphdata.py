# -*- coding: utf-8 -*-"
"""
    savegraphdata class for saving the semantic data of pages

    @copyright: 2006 by Juhani Eronen <exec@iki.fi>
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

from time import time
from copy import copy

# MoinMoin imports
from MoinMoin.parser.text_moin_wiki import Parser
from MoinMoin.wikiutil import importPlugin, get_processing_instructions
from MoinMoin.Page import Page 

# graphlib imports
from graphingwiki.util import node_type, SPECIAL_ATTRS, NO_TYPE, delete_moin_caches
from graphingwiki.editing import parse_categories


def parse_text(request, page, text):
    pagename = page.page_name
    
    from copy import copy
    newreq = copy(request)
    newreq.cfg = copy(request.cfg)
    newreq.page = lcpage = LinkCollectingPage(newreq, pagename, text)
    newreq.theme = copy(request.theme)
    newreq.theme.request = newreq
    newreq.theme.cfg = newreq.cfg
    parserclass = importPlugin(request.cfg, "parser",
                                   'link_collect', "Parser")
    import MoinMoin.wikiutil as wikiutil
    myformatter = wikiutil.importPlugin(request.cfg, "formatter",
                                      'nullformatter', "Formatter")
    lcpage.formatter = myformatter(newreq)
    lcpage.formatter.page = lcpage
    p = parserclass(lcpage.get_raw_body(), newreq, formatter=lcpage.formatter)
    lcpage.parser = p
    lcpage.format(p)
    
    # These are the match types that really should be noted
    linktypes = ["wikiname_bracket", "word",                  
                 "interwiki", "url", "url_bracket"]
    
    new_data = {}

    # Add the page categories as links too
    categories, _, _ = parse_categories(request, text)

    # Process ACL:s
    pi, _ = get_processing_instructions(text)
    for verb, args in pi:
        if verb == u'acl':
            # Add all ACL:s on multiple lines to an one-lines
            acls = new_data.get(pagename, dict()).get('acl', '')
            acls = acls.strip() + args
            new_data.setdefault(pagename, dict())['acl'] = acls

    for metakey, value in p.definitions.iteritems():
        for type, item in value:
            # print metakey, type, item
            dnode = None

            if  type in ['url', 'wikilink', 'interwiki', 'email']:
                dnode = item[1]
                hit = item[0]
            elif type == 'category':
                # print "adding cat", item, repr(categories)
                dnode = item
                hit = item
                if item in categories:
                    request.graphdata.add_link(new_data, pagename, dnode, 
                             u"gwikicategory")
            elif type == 'meta':
                add_meta(new_data, pagename, (metakey, item))
            elif type == 'include':
                # No support for regexp includes, for now!
                if not item[0].startswith("^"):
                    included = wikiutil.AbsPageName(pagename, item[0])
                    request.graphdata.add_link(new_data, pagename, included, u"gwikiinclude")

            if dnode:
                request.graphdata.add_link(new_data, pagename, dnode, metakey)

    return new_data

def strip_meta(key, val):
    key = key.strip()
    val = val.strip()

    # retain empty labels
    if key == 'gwikilabel' and not val:
        val = ' '        

    return key, val

def set_attribute(new_data, node, key, val):
    key, val = strip_meta(key, val)

    temp = new_data.get(node, {})

    if not temp.has_key(u'meta'):
        temp[u'meta'] = {key: [val]}
    elif not temp[u'meta'].has_key(key):
        temp[u'meta'][key] = [val]
    # a page can not have more than one label, shapefile etc
    elif key in SPECIAL_ATTRS:
        temp[u'meta'][key] = [val]
    else:
        temp[u'meta'][key].append(val)

    new_data[node] = temp

def add_meta(new_data, pagename, (key, val)):

    # Do not handle empty metadata, except empty labels
    val = val.strip()
    if key == 'gwikilabel' and not val:
        val = ' '        

    if not val:
        return

    # Values to be handled in graphs
    if key in SPECIAL_ATTRS:
        set_attribute(new_data, pagename, key, val)
        # If color defined, set page as filled
        if key == 'fillcolor':
            set_attribute(new_data, pagename, 'style', 'filled')
        return

    # Save to shelve's metadata list
    set_attribute(new_data, pagename, key, val)

def changed_meta(request, pagename, old_data, new_data):
    add_out = dict()
    del_out = dict()

    add_in = dict()
    del_in = dict()

    for page in new_data:
        add_in.setdefault(page, list())
        del_in.setdefault(page, list())

    # Code for making out which edges have changed.
    # We only want to save changes, not all the data,
    # as edges have a larger time footprint while saving.

    add_out.setdefault(pagename, list())
    del_out.setdefault(pagename, list())

    old_keys = set(old_data.get(u'out', {}).keys())
    new_keys = set(new_data.get(pagename, {}).get(u'out', {}).keys())
    changed_keys = old_keys.intersection(new_keys)

    # Changed edges == keys whose values have experienced changes
    for key in changed_keys:
        new_edges = len(new_data[pagename][u'out'][key])
        old_edges = len(old_data[u'out'][key])

        for i in range(max(new_edges, old_edges)):

            # old data had more links, delete old
            if new_edges <= i:
                val = old_data[u'out'][key][i]

                del_out[pagename].append((key, val))

                # Only local pages will have edges and metadata
                if node_type(request, val) == 'page':
                    del_in.setdefault(val, list()).append((key, pagename))

            # new data has more links, add new
            elif old_edges <= i:
                val = new_data[pagename][u'out'][key][i]

                add_out[pagename].append((key, val))

                # Only save in-links to local pages, not eg. url or interwiki
                if node_type(request, val) == 'page':
                    add_in.setdefault(val, list()).append((key, pagename))

            # check if the link i has changed
            else:
                val = old_data[u'out'][key][i]
                new_val = new_data[pagename][u'out'][key][i]

                if val == new_val:
                    continue

                # link changed, replace old link with new
                # add and del out-links
                add_out[pagename].append((key, new_val))

                del_out[pagename].append((key, val))

                # Only save in-links to local pages, not eg. url or interwiki
                if node_type(request, new_val) == 'page':
                    add_in.setdefault(new_val, list()).append((key, pagename))
                # Only save in-links to local pages, not eg. url or interwiki
                if node_type(request, val) == 'page':
                    del_in.setdefault(val, list()).append((key, pagename))

    # Added edges of a new linktype
    for key in new_keys.difference(old_keys):
        for i, val in enumerate(new_data[pagename][u'out'][key]):

            add_out[pagename].append((key, val))

            # Only save in-links to local pages, not eg. url or interwiki
            if node_type(request, val) == 'page':
                add_in.setdefault(val, list()).append((key, pagename))

    # Deleted edges
    for key in old_keys.difference(new_keys):
        for val in old_data.get(u'out')[key]:

            del_out[pagename].append((key, val))

            # Only local pages will have edges and metadata
            if node_type(request, val) == 'page':
                del_in.setdefault(val, list()).append((key, pagename))

    # Adding and removing in-links are the most expensive operation in a
    # shelve, so we'll try to minimise them. Eg. if page TestPage is
    #  a:: ["b"]\n a:: ["a"] 
    # and it is resaved as
    #  a:: ["a"]\n a:: ["b"]
    # the ordering of out-links in TestPage changes, but we do not have
    # to touch the in-links in pages a and b. This is possible because
    # in-links do not have any sensible order.
    for page in new_data:
        #print repr(page), add_in[page], del_in[page]

        changes = set(add_in[page] + del_in[page])

        #print changes

        for key, val in changes:
            #print 'change', repr(key), repr(val)

            add_count = add_in[page].count((key, val))
            del_count = del_in[page].count((key, val))

            if not add_count or not del_count:
                #print "No changes"
                #print
                continue

            change_count = add_count - del_count

            # If in-links added and deleted as many times, 
            # there are effectively no changes to be saved
            if change_count == 0:
                for x in range(add_count):
                    add_in[page].remove((key, val))
                    del_in[page].remove((key, val))
                    #print "No changes"

            elif change_count < 0:
                for x in range(abs(change_count)):
                    del_in[page].remove((key, val))
                    #print "No need to delete %s from %s" % (val, page)

            else:
                for x in range(abs(change_count)):
                    #print "No need to add %s to %s" % (val, page)
                    add_in[page].remove((key, val))

            #print

    #print

    return add_out, del_out, add_in, del_in

def _clear_page(request, pagename):
    # Do not delete in-links! It will break graphs, categories and whatnot
    if not request.graphdata[pagename].get('in', {}):
        del request.graphdata[pagename]
    else:
        request.graphdata[pagename][u'saved'] = False
        del request.graphdata[pagename][u'mtime']
        del request.graphdata[pagename][u'acl']
        del request.graphdata[pagename][u'meta']

def execute(pagename, request, text, pagedir, pageitem):
    # Skip MoinEditorBackups
    if pagename.endswith('/MoinEditorBackup'):
        return

    
    # parse_text, add_link, add_meta return dict with keys like
    # 'BobPerson' -> {u'out': {'friend': ['GeorgePerson']}}
    # (ie. same as what graphdata contains)

    # Get new data from parsing the page
    new_data = parse_text(request, pageitem, text)

    # Get a copy of current data
    old_data = request.graphdata.getpage(pagename)

    changed_new_out, changed_del_out, changed_new_in, changed_del_in = \
        changed_meta(request, pagename, old_data, new_data)

    # Insert metas and other stuff from parsed content
    cur_time = time()

    request.graphdata.set_page_meta_and_acl_and_mtime_and_saved(pagename,
                                                                new_data.get(pagename, dict()).get(u'meta', dict()),
                                                                new_data.get(pagename, dict()).get(u'acl', ''),
                                                                cur_time, True)

    # Save the links that have truly changed
    for page in changed_del_out:
        for edge in changed_del_out[page]:
            #print 'delout', repr(page), edge
            linktype, dst = edge
            request.graphdata.remove_out(request.graphdata, [page, dst], [linktype])

    for page in changed_del_in:
        for edge in changed_del_in[page]:
            #print 'delin', repr(page), edge
            linktype, src = edge
            request.graphdata.remove_in(request.graphdata, [src, page], [linktype])

    for page in changed_new_out:
        for i, edge in enumerate(changed_new_out[page]):
            linktype, dst = edge
            #print 'addout', repr(page), edge
            request.graphdata.add_out(request.graphdata, [page, dst], linktype)

    for page in changed_new_in:
        for edge in changed_new_in[page]:
            #print 'addin', repr(page), edge
            linktype, src = edge
            request.graphdata.add_in(request.graphdata, [src, page], linktype)

    ## Remove deleted pages from the shelve
    # 1. Removing data at the moment of deletion
    # Deleting == saving a revision with the text 'deleted/n', then 
    # removing the revision. This seems to be the only way to notice.
    if text == 'deleted\n':
        _clear_page(request, pagename)
    else:
        # 2. Removing data when rehashing. 
        # New pages do not exist, but return a revision of 99999999 ->
        # Check these both to avoid deleting new pages.
        pf, rev, exists = pageitem.get_rev() 
        if rev != 99999999:
            if not exists:
                _clear_page(request, pagename)

    delete_moin_caches(request, pageitem)

# - code below lifted from MetaFormEdit -

# Override Page.py to change the parser. This method has the advantage
# that it works regardless of any processing instructions written on
# page, including the use of other parsers
class LinkCollectingPage(Page):
    def __init__(self, request, page_name, content, **keywords):
        # Cannot use super as the Moin classes are old-style
        apply(Page.__init__, (self, request, page_name), keywords)
        self.set_raw_body(content)

    # It's important not to cache this, as the wiki thinks we are
    # using the default parser
    def send_page_content(self, request, notparser, body, format_args='',
                          do_cache=0, **kw):
        self.parser = wikiutil.importPlugin(request.cfg, "parser",
                                       'link_collect', "Parser")

        kw['format_args'] = format_args
        kw['do_cache'] = 0
        apply(Page.send_page_content, (self, request, self.parser, body), kw)
