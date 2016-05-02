import os

from wikitextutil import parse_text

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
            pf, rev, exists = pageitem.get_rev(auto_underlay=True)
            if rev != 99999999:
                if not exists:
                    request.graphdata.clear_page(request, pagename)

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
    oldpath = page.getPagePath(check_create=False)
    for dirpath, dirs, files in os.walk(oldpath, topdown=False):
        # If there are files left, some backups etc information is
        # still there, so let's quit
        if files:
            break

        os.rmdir(dirpath)
