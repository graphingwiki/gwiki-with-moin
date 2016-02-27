# -*- coding: utf-8 -*-"
"""
    class for handling page metadata

    @copyright: 2006-2016 by Jussi Eronen <exec@iki.fi>
"""
import os

from time import time

from MoinMoin.wikiutil import get_processing_instructions, AbsPageName
from MoinMoin.Page import LinkCollectingPage
from MoinMoin import config
from MoinMoin import caching
from MoinMoin.parser.link_collect import Parser as lcparser

from util import node_type, SPECIAL_ATTRS, NO_TYPE
from wikitextutil import parse_categories, parse_text

def savegraphdata(pagename, request, text, pagedir, pageitem):
    try:
        # Skip MoinEditorBackups
        if pagename.endswith('/MoinEditorBackup'):
            return

        # parse_text, add_link, add_meta return dict with keys like
        # 'BobPerson' -> {u'out': {'friend': ['GeorgePerson']}}
        # (ie. same as what graphdata contains)

        # Get new data from parsing the page
        new_data = parse_text(request, pageitem, text)

        request.graphdata.set_page(request, pagename, new_data)

        ## Remove deleted pages from the backend
        # 1. Removing data at the moment of deletion
        # Deleting == saving a revision with the text 'deleted/n', then 
        # removing the revision. This seems to be the only way to notice.
        if text == 'deleted\n':
            request.graphdata.clear_page(request, pagename)
        else:
            # 2. Removing data when rehashing. 
            # New pages do not exist, but return a revision of 99999999 ->
            # Check these both to avoid deleting new pages.
            pf, rev, exists = pageitem.get_rev() 
            if rev != 99999999:
                if not exists:
                    _clear_page(request, pagename)

        pageitem.delete_caches()
        request.graphdata.post_save(pagename)
    except:
        request.graphdata.abort()
        raise

def underlay_to_pages(req, p):
    underlaydir = req.cfg.data_underlay_dir

    pagepath = p.getPagePath()

    # If the page has not been created yet, create its directory and
    # save the stuff there
    if underlaydir in pagepath:
        pagepath = pagepath.replace(underlaydir, pagepath)
        if not os.path.exists(pagepath):
            os.makedirs(pagepath)

    return pagepath

# Functions for properly opening, closing, saving and deleting
# graphdata.
def graphdata_getter(self):
#    from graphingwiki.backend.couchdbclient import GraphData
#    from graphingwiki.backend.durusclient import GraphData
    from MoinMoin.metadata.backend.shelvedb import GraphData
    if "_graphdata" not in self.__dict__:
        dbconfig = getattr(self.cfg, 'dbconfig', {})
        if "dbname" not in dbconfig:
            dbconfig["dbname"] = self.cfg.interwikiname

        self.__dict__["_graphdata"] = GraphData(self, **dbconfig)
    return self.__dict__["_graphdata"]

def graphdata_close(self):
    graphdata = self.__dict__.pop("_graphdata", None)
    if graphdata is not None:
        graphdata.commit()
        graphdata.close()

def graphdata_commit(self, *args):
    graphdata = self.__dict__.pop("_graphdata", None)
    if graphdata is not None:
        graphdata.commit()

## XXX: Hook PageEditor.sendEditor to add data on template to the
## text of the saved page?
def graphdata_save(page):
    text = page.get_raw_body()
    path = underlay_to_pages(page.request, page)

    savegraphdata(page.page_name, page.request, text, path, page)

def graphdata_copy(page, newpagename):
    text = page.get_raw_body()
    path = underlay_to_pages(page.request, page)

    savegraphdata(newpagename, page.request, text, path, page)

# Note: PageEditor.renamePage seems to use .saveText for the new
# page (thus already updating the page's metas), so only the old page's
# metas need to be deleted explicitly.
def graphdata_rename(page):
    path = underlay_to_pages(page.request, page)

    # Rename is really filesystem-level rename, no old data is really
    # left behind, so it should be cleared.  When saving with text
    # 'deleted\n', no graph data is actually saved.
    savegraphdata(page.page_name, page.request, 'deleted\n', path, page)

    # Rename might litter empty directories data/pagename and
    # data/pagename/cache, let's remove them
    oldpath = page.getPagePath(check_create=0)
    for dirpath, dirs, files in os.walk(oldpath, topdown=False):
        # If there are files left, some backups etc information is
        # still there, so let's quit
        if files:
            break

        os.rmdir(dirpath)

# Fetch requested metakey value for the given page.
def get_metas(request, name, metakeys, checkAccess=True, 
              includeGenerated=True, formatLinks=False, **kw):
    if not includeGenerated:
        metakeys = [x for x in metakeys if not '->' in x]

    metakeys = set(metakeys)
    pageMeta = dict([(key, list()) for key in metakeys])

    if checkAccess:
        if not request.user.may.read(name):
            return pageMeta

    loadedPage = request.graphdata.getpage(name)

    # Make a real copy of loadedOuts and loadedMeta for tracking indirection
    loadedOuts = dict()
    outs = request.graphdata.get_out(name)
    for key in outs:
        loadedOuts[key] = list(outs[key])

    loadedMeta = dict()
    metas = request.graphdata.get_meta(name)
    for key in metas:
        loadedMeta.setdefault(key, list())
        if formatLinks:
            values = metas_to_abs_links(request, name, metas[key])
        else:
            values = metas[key]
        loadedMeta[key].extend(values)

    loadedOutsIndir = dict()
    for key in loadedOuts:
        loadedOutsIndir.setdefault(key, set()).update(loadedOuts[key])

    if includeGenerated:
        # Handle inlinks separately
        if 'gwikiinlinks' in metakeys:
            inLinks = inlinks_key(request, loadedPage, checkAccess=checkAccess)

            loadedOuts['gwikiinlinks'] = inLinks

        # Meta key indirection support
        for key in metakeys:
            add_matching_redirs(request, loadedPage, loadedOuts, 
                                loadedMeta, metakeys,
                                key, name, key, formatLinks)

    # Add values
    for key in metakeys & set(loadedMeta):
        for value in loadedMeta[key]:
            pageMeta[key].append(value)

    # Add gwikicategory as a special case, as it can be metaedited
    if loadedOuts.has_key('gwikicategory'):
        # Empty (possible) current gwikicategory to fix a corner case
        pageMeta['gwikicategory'] = loadedOuts['gwikicategory']
            
    return pageMeta

def add_matching_redirs(request, loadedPage, loadedOuts, loadedMeta,
                        metakeys, key, curpage, curkey,
                        prev='', formatLinks=False, linkdata=None):
    if not linkdata:
        linkdata = dict()
    args = curkey.split('->')

    inlink = False
    if args[0] == 'gwikiinlinks':
        inlink = True
        args = args[1:]

    newkey = '->'.join(args[2:])

    last = False

    if not args:
        return
    if len(args) in [1, 2]:
        last = True

    if len(args) == 1:
        linked, target_key = prev, args[0]
    else:
        linked, target_key = args[:2]

    if inlink:
        pages = request.graphdata.get_in(curpage).get(linked, set())
    else:
        pages = request.graphdata.get_out(curpage).get(linked, set())

    for indir_page in set(pages):
        # Relative pages etc
        indir_page = wikiutil.AbsPageName(request.page.page_name,
                                          indir_page)

        if request.user.may.read(indir_page):
            pagedata = request.graphdata.getpage(indir_page)

            outs = pagedata.get('out', dict())
            metas = pagedata.get('meta', dict())

            # Add matches at first round
            if last:
                if target_key in metas:
                    loadedMeta.setdefault(key, list())
                    linkdata.setdefault(key, dict())
                    if formatLinks:
                        values = metas_to_abs_links(
                            request, indir_page, metas[target_key])
                    else:
                        values = metas[target_key]
                    loadedMeta[key].extend(values)
                    linkdata[key].setdefault(indir_page, list()).extend(values)
                else:
                    linkdata.setdefault(key, dict())
                    linkdata[key].setdefault(indir_page, list())
                continue

            elif not target_key in outs:
                continue

            # Handle inlinks separately
            if 'gwikiinlinks' in metakeys:
                inLinks = inlinks_key(request, loadedPage,
                                      checkAccess=checkAccess)

                loadedOuts[key] = inLinks
                continue

            linkdata = add_matching_redirs(request, loadedPage, loadedOuts,
                                           loadedMeta, metakeys, key,
                                           indir_page, newkey, target_key,
                                           formatLinks, linkdata)

    return linkdata
