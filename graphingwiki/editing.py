# -*- coding: utf-8 -*-
"""
    Graphingwiki editing functions
     - Saving page contents or relevant metadata

    @copyright: 2007 by Juhani Eronen, Erno Kuusela and Joachim Viide
    @license: MIT <http://www.opensource.org/licenses/mit-license.php>
"""
import os
import re
import string
import socket
import copy

try:
    from hashlib import md5
except ImportError:
    from md5 import md5

from MoinMoin.action.AttachFile import getAttachDir, getFilename, _addLogEntry
from MoinMoin.PageEditor import PageEditor
from MoinMoin.Page import Page
from MoinMoin import wikiutil
from MoinMoin import config
from MoinMoin import caching
from MoinMoin.wikiutil import importPlugin, AbsPageName

from graphingwiki.util import filter_categories
from graphingwiki.util import SPECIAL_ATTRS, editable_p
from graphingwiki.util import category_regex, template_regex

def macro_re(macroname):
    return re.compile(r'(?<!#)\s*?\[\[(%s)\((.*?)\)\]\]' % macroname)

metadata_re = macro_re("MetaData")

# These are the match types for links that really should be noted
linktypes = ["wikiname_bracket", "word",
             "interwiki", "url", "url_bracket"]


def get_revisions(request, page, checkAccess=True):
    pagename = page.page_name
    if checkAccess and not request.user.may.read(pagename):
        return [], []

    parse_text = importPlugin(request.cfg,
                              'action',
                              'savegraphdata',
                              'parse_text')

    alldata = dict()
    revisions = dict()
    
    for rev in page.getRevList():
        revlink = '%s-gwikirevision-%d' % (pagename, rev)

        # Data about revisions is now cached to the graphdata
        # at the same time this is used.
        if request.graphdata.has_key(revlink):
            revisions[rev] = revlink
            continue

        # If not cached, parse the text for the page
        revpage = Page(request, pagename, rev=rev)
        text = revpage.get_raw_body()
        alldata = parse_text(request, revpage, text)
        if alldata.has_key(pagename):
            alldata[pagename].setdefault('meta',
                                         dict())[u'gwikirevision'] = \
                                         [unicode(rev)]
            # Do the cache.
            request.graphdata.cacheset(revlink, alldata[pagename])

            # Add revision as meta so that it is shown in the table
            revisions[rev] = revlink

    pagelist = [revisions[x] for x in sorted(revisions.keys(),
                                             key=ordervalue,
                                             reverse=True)]

    metakeys = set()
    for page in pagelist:
        for key in request.graphdata.get_metakeys(page):
            metakeys.add(key)
    metakeys = sorted(metakeys, key=ordervalue)

    return pagelist, metakeys


def getmeta_to_table(input):
    keyoccur = dict()

    keys = list()
    for key in input[0]:
        keyoccur[key] = 1
        keys.append(key)

    for row in input[1:]:
        for i, key in enumerate(row[1:]):
            keylen = len(key)
            if keylen > keyoccur[keys[i]]:
                keyoccur[keys[i]] = keylen

    table_keys = ['Page name']

    for key in input[0]:
        table_keys.extend([key] * keyoccur[key])

    table = [table_keys]

    for vals in input[1:]:
        row = [vals[0]]
        for i, val in enumerate(vals[1:]):
            val.extend([''] * (keyoccur[keys[i]] - len(val)))
            row.extend(val)
        table.append(row)

    return table

# Fetch only the link information for the selected page
def get_links(request, name, metakeys, checkAccess=True, **kw):
    metakeys = set([x for x in metakeys if not '->' in x])
    pageLinks = dict([(key, list()) for key in metakeys])

    loadedPage = request.graphdata.getpage(name)

    loadedOuts = loadedPage.get("out", dict())

    # Add values
    for key in metakeys & set(loadedOuts):
        for value in loadedOuts[key]:
            pageLinks[key].append(value)
            
    return pageLinks

def iter_metas(request, rule, keys=None, checkAccess=True):
    from abusehelper.core import rules, events
    if type(rule) != rules.rules.Match:
        rule = rules.parse(unicode(rule))

    for page, _meta in request.graphdata.items():
        _page = {u"gwikipagename": page}
        metas = _meta.get(u"meta", None)

        if checkAccess and not request.user.may.read(page):
            continue

        if not metas:
            continue

        _out = request.graphdata.get_out(page)
        if _out.has_key('gwikicategory'):
            metas.setdefault(u'gwikicategory', []).extend(_out.get("gwikicategory"))

        data = events.Event(dict(metas.items() + _page.items()))
        if rule.match(data):
            if keys:
                metas = dict((key, metas.get(key, list())) for key in keys)

            yield page, metas


# Fetch metas matching abuse-sa filter rule
def get_metas2(request, rule, keys=None, checkAccess=True):
    results = dict()
    for page, metas in iter_metas(request, rule, keys, checkAccess):
        results[page] = metas

    return results

def get_pages(request):
    def group_filter(name):
        # aw crap, SystemPagesGroup is not a system page
        if name == 'SystemPagesGroup':
            return False
        if wikiutil.isSystemPage(request, name):
            return False
        return request.user.may.read(name)

    return request.rootpage.getPageList(filter=group_filter)

def edit_meta(request, pagename, oldmeta, newmeta):
    page = PageEditor(request, pagename)

    text = page.get_raw_body()
    text = replace_metas(request, text, oldmeta, newmeta)

    # PageEditor.saveText doesn't allow empty texts
    if not text:
        text = u" "

    try:
        msg = page.saveText(text, 0)
    except page.Unchanged:
        msg = u'Unchanged'

    return msg

def set_metas(request, cleared, discarded, added):
    pages = set(cleared) | set(discarded) | set(added)

    # Discard empties and junk
    pages = [wikiutil.normalize_pagename(x, request.cfg) for x in pages]
    pages = [x for x in pages if x]

    msg = list()

    # We don't have to check whether the user is allowed to read
    # the page, as we don't send any info on the pages out. Only
    # check that we can write to the requested pages.
    for page in pages:
        if not request.user.may.write(page):
            message = "You are not allowed to edit page '%s'" % page
            return False, request.getText(message)

    for page in pages:
        pageCleared = cleared.get(page, set())
        pageDiscarded = discarded.get(page, dict())
        pageAdded = added.get(page, dict())
        
        # Template clears might make sense at some point, not implemented
        if TEMPLATE_KEY in pageCleared:
            pageCleared.remove(TEMPLATE_KEY)
        # Template changes might make sense at some point, not implemented
        if TEMPLATE_KEY in pageDiscarded:
            del pageDiscarded[TEMPLATE_KEY]
        # Save templates for empty pages
        if TEMPLATE_KEY in pageAdded:
            save_template(request, page, ''.join(pageAdded[TEMPLATE_KEY]))
            del pageAdded[TEMPLATE_KEY]

        metakeys = set(pageCleared) | set(pageDiscarded) | set(pageAdded)
        # Filter out uneditables, such as inlinks
        metakeys = editable_p(metakeys)

        old = get_metas(request, page, metakeys, 
                        checkAccess=False, includeGenerated=False)

        new = dict()
        for key in old:
            values = old.pop(key)
            old[key] = values
            new[key] = set(values)
        for key in pageCleared:
            new[key] = set()
        for key, values in pageDiscarded.iteritems():
            for v in values:
                new[key].difference_update(values) 

        for key, values in pageAdded.iteritems():
            new[key].update(values)

        for key, values in new.iteritems():
            ordered = copy.copy(old[key])
            
            for index, value in enumerate(ordered):
                if value not in values:
                    ordered[index] = u""

            values.difference_update(ordered)
            ordered.extend(values)
            new[key] = ordered

        msg.append(edit_meta(request, page, old, new))

    return True, msg

def save_template(request, page, template):
    # Get body, or template if body is not available, or ' '
    raw_body = Page(request, page).get_raw_body()
    msg = ''
    if not raw_body:
        # Start writing

        ## TODO: Add data on template to the text of the saved page?

        raw_body = ' '
        p = PageEditor(request, page)
        template_page = wikiutil.unquoteWikiname(template)
        if request.user.may.read(template_page):
            temp_body = Page(request, template_page).get_raw_body()
            if temp_body:
                raw_body = temp_body

        msg = p.saveText(raw_body, 0)

    return msg

# You can implement different coordinate formats here
COORDINATE_REGEXES = [
    # long, lat -> to itself
    ('(-?\d+\.\d+,-?\d+\.\d+)', lambda x: x.group())
    ]
def verify_coordinates(coords):
    for regex, replacement in COORDINATE_REGEXES:
        if re.match(regex, coords):
            try:
                retval = re.sub(regex, replacement, coords)
                return retval
            except:
                pass

def check_attachfile(request, pagename, aname):
    # Check that the attach dir exists
    getAttachDir(request, pagename, create=1)
    aname = wikiutil.taintfilename(aname)
    fpath = getFilename(request, pagename, aname)

    # Trying to make sure the target is a regular file
    if os.path.isfile(fpath) and not os.path.islink(fpath):
        return fpath, True

    return fpath, False

def save_attachfile(request, pagename, content, aname, 
                    overwrite=False, log=False):
    try:
        fpath, exists = check_attachfile(request, pagename, aname)
        if not overwrite and exists:
            return False

        # Save the data to a file under the desired name
        stream = open(fpath, 'wb')
        stream.write(content)
        stream.close()

        if log:
            _addLogEntry(request, 'ATTNEW', pagename, aname)
    except:
        return False

    return True

def load_attachfile(request, pagename, aname):
    try:
        fpath, exists = check_attachfile(request, pagename, aname)
        if not exists:
            return None

        # Load the data from the file
        stream = open(fpath, 'rb')
        adata = stream.read()
        stream.close()
    except:
        return None

    return adata

def delete_attachfile(request, pagename, aname, log=False):
    try:
        fpath, exists = check_attachfile(request, pagename, aname)
        if not exists:
            return False

        os.unlink(fpath)

        if log:
            _addLogEntry(request, 'ATTDEL', pagename, aname)
    except:
        return False

    return True

def list_attachments(request, pagename):
    # Code from MoinMoin/action/AttachFile._get_files
    attach_dir = getAttachDir(request, pagename)
    if os.path.isdir(attach_dir):
        files = map(lambda a: a.decode(config.charset), os.listdir(attach_dir))
        files.sort()
        return files

    return []

# FIXME this should probably include all the formatters beyond the
# default install. The problem is that there does not seem to be a
# good way for listing them. However, in testing, I did not find a way
# to cache the output of the other formatters by just using the wiki,
# so already this could work for most cases.
CACHE_AUTOMATED = ['pagelinks', 'text_html', 'text_html_percent',
                   'dom_xml', 'text_plain', 'text_docbook', 'text_gedit',
                   'text_python', 'text_xml']

# Caching functions for items in the page cache, should they be needed
# in other code. Sendcache manipulation functions can be found in
# util.
def check_pagecachefile(request, pagename, cfname):
    page = Page(request, pagename)
    data_cache = caching.CacheEntry(request, page, cfname, 
                                    scope='item', do_locking=True)
    return data_cache, data_cache.exists()

def save_pagecachefile(request, pagename, content, cfname, overwrite=False):
    try:
        entry, exists = check_pagecachefile(request, pagename, cfname)
        if not overwrite and exists:
            return False

        # Do not save over MoinMoin autogenerated page cache files,
        # having arbitrary data there will probably only result in
        # crashes. Deleting these files is ok though.
        if cfname in CACHE_AUTOMATED:
            return False

        # Save the data to a file under the desired name
        entry.open(mode='wb')
        entry.write(content)
        entry.close()
    except caching.CacheError:
        return False

    return True


def load_pagecachefile(request, pagename, cfname):
    try:
        entry, exists = check_pagecachefile(request, pagename, cfname)
        if not exists:
            return None

        # Load data from the cache file
        entry.open(mode='rb')
        cfdata = entry.read()
        entry.close()
    except caching.CacheError:
        return None

    return cfdata


def delete_pagecachefile(request, pagename, cfname):
    try:
        entry, exists = check_pagecachefile(request, pagename, cfname)
        if not exists:
            return False

        entry.remove()
    except caching.CacheError:
        return False

    return True


def list_pagecachefiles(request, pagename):
    page = Page(request, pagename)
    return caching.get_cache_list(request, page, 'item')


def _doctest_request(graphdata=dict(), mayRead=True, mayWrite=True):
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


def _test():
    import doctest
    doctest.testmod()

if __name__ == "__main__":
    _test()
