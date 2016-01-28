# -*- coding: utf-8 -*-"
"""
    class for handling page metadata

    @copyright: 2006-2016 by Jussi Eronen <exec@iki.fi>
"""
from time import time

from MoinMoin.wikiutil import get_processing_instructions
from MoinMoin.Page import LinkCollectingPage
from MoinMoin.wikiutil import AbsPageName
from MoinMoin import config
from MoinMoin import caching
from MoinMoin.parser.link_collect import Parser as lcparser

from util import node_type, SPECIAL_ATTRS, NO_TYPE
from wikitextutil import parse_categories, parse_text

def strip_meta(key, val):
    key = key.strip()
    val = val.strip()

    # retain empty labels
    if key == 'gwikilabel' and not val:
        val = ' '        

    return key, val

def add_link(new_data, pagename, nodename, linktype):
    edge = [pagename, nodename]

    add_in(new_data, edge, linktype)
    add_out(new_data, edge, linktype)


def add_in(new_data, (frm, to), linktype):
    "Add in-links from current node to local nodes"

    if hasattr(new_data, 'add_in'):
        new_data.add_in((frm, to), linktype)
        return

    if not linktype:
        linktype = NO_TYPE

    temp = new_data.get(to, {})

    if not temp.has_key(u'in'):
        temp[u'in'] = {linktype: [frm]}
    elif not temp[u'in'].has_key(linktype):
        temp[u'in'][linktype] = [frm]
    else:
        temp[u'in'][linktype].append(frm)

    # Notification that the destination has changed
    temp[u'mtime'] = time()
    
    new_data[to] = temp


def add_out(new_data, (frm, to), linktype):
    "Add out-links from local nodes to current node"

    if hasattr(new_data, 'add_out'):
        new_data.add_out((frm, to), linktype)
        return

    if not linktype:
        linktype = NO_TYPE

    temp = new_data.get(frm, {})
    
    if not temp.has_key(u'out'):
        temp[u'out'] = {linktype: [to]}
    elif not temp[u'out'].has_key(linktype):
        temp[u'out'][linktype] = [to]
    else:
        temp[u'out'][linktype].append(to)

    new_data[frm] = temp


def remove_in(new_data, (frm, to), linktype):
    "Remove in-links from local nodes to current node"

    if hasattr(new_data, 'remove_in'):
        new_data.remove_in((frm, to), linktype)
        return

    temp = new_data.getpage(to)
    if not temp.has_key(u'in'):
        return

    for type in linktype:
        # sys.stderr.write("Removing %s %s %s\n" % (frm, to, linktype))
        # eg. when the shelve is just started, it's empty
        if not temp[u'in'].has_key(type):
            # sys.stderr.write("No such type: %s\n" % type)
            continue
        if frm in temp[u'in'][type]:
            temp[u'in'][type].remove(frm)

            # Notification that the destination has changed
            temp[u'mtime'] = time()

        if not temp[u'in'][type]:
            del temp[u'in'][type]


    # sys.stderr.write("Hey man, I think I did it!\n")
    new_data[to] = temp

def remove_out(new_data, (frm, to), linktype):
    "remove outlinks"

    if hasattr(new_data, 'remove_out'):
        new_data.remove_out((frm, to), linktype)
        return

    temp = new_data.get(frm, {})
    
    if not temp.has_key(u'out'):
        return 

    for type in linktype:
        # print "Removing %s %s %s" % (frm, to, linktype)
        # eg. when the shelve is just started, it's empty
        if not temp[u'out'].has_key(type):
            # print "No such type: %s" % type
            continue
        if to in temp[u'out'][type]:
            i = temp[u'out'][type].index(to)
            del temp[u'out'][type][i]

            # print "removed %s" % (repr(to))

        if not temp[u'out'][type]:
            del temp[u'out'][type]
            # print "%s empty" % (type)
            # print "Hey man, I think I did it!"

    new_data[frm] = temp


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

# class dict_with_getpage(dict):
#     def getpage(self, pagename):
#         return self.setdefault(pagename, {})

#     def add_out(self, frm, to, linktype):
#         if not self.has_key(u'out'):
#             self[u'out'] = {linktype: [to]}
#         elif not self[u'out'].has_key(linktype):
#             self[u'out'][linktype] = [to]
#         else:
#             self[u'out'][linktype].append(to)

dict_with_getpage = dict

def changed_meta(request, pagename, old_outs, new_data):
    add_out = dict_with_getpage()
    del_out = dict_with_getpage()

    add_in = dict_with_getpage()
    del_in = dict_with_getpage()

    for page in new_data:
        add_in.setdefault(page, list())
        del_in.setdefault(page, list())

    # Code for making out which edges have changed.
    # We only want to save changes, not all the data,
    # as edges have a larger time footprint while saving.

    add_out.setdefault(pagename, list())
    del_out.setdefault(pagename, list())

    old_keys = set(old_outs.keys())
    new_keys = set(new_data.get(pagename, {}).get(u'out', {}).keys())
    changed_keys = old_keys.intersection(new_keys)

    # Changed edges == keys whose values have experienced changes
    for key in changed_keys:
        new_edges = len(new_data[pagename][u'out'][key])
        old_edges = len(old_outs[key])

        for i in range(max(new_edges, old_edges)):

            # old data had more links, delete old
            if new_edges <= i:
                val = old_outs[key][i]

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
                val = old_outs[key][i]
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
        for val in old_outs[key]:

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
    if hasattr(request.graphdata, 'clear_page'):
        request.graphdata.clear_page(pagename)
        return
    # Do not delete in-links! It will break graphs, categories and whatnot
    if not request.graphdata[pagename].get('in', {}):
        del request.graphdata[pagename]
    else:
        request.graphdata[pagename][u'saved'] = False
        del request.graphdata[pagename][u'mtime']
        del request.graphdata[pagename][u'acl']
        del request.graphdata[pagename][u'meta']

def savegraphdata_execute(pagename, request, text, pagedir, pageitem):
    try:
        return savegraphdata_execute2(pagename, request, text, pagedir, pageitem)
    except:
        request.graphdata.abort()
        raise

def savegraphdata_execute2(pagename, request, text, pagedir, pageitem):
    # Skip MoinEditorBackups
    if pagename.endswith('/MoinEditorBackup'):
        return
    
    # parse_text, add_link, add_meta return dict with keys like
    # 'BobPerson' -> {u'out': {'friend': ['GeorgePerson']}}
    # (ie. same as what graphdata contains)

    # Get new data from parsing the page
    new_data = parse_text(request, pageitem, text)

    # Get a copy of current data
    old_outs = request.graphdata.get_out(pagename)

    changed_new_out, changed_del_out, changed_new_in, changed_del_in = \
        changed_meta(request, pagename, old_outs, new_data)

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
            remove_out(request.graphdata, [page, dst], [linktype])

    for page in changed_del_in:
        for edge in changed_del_in[page]:
            #print 'delin', repr(page), edge
            linktype, src = edge
            remove_in(request.graphdata, [src, page], [linktype])

    for page in changed_new_out:
        for i, edge in enumerate(changed_new_out[page]):
            linktype, dst = edge
            #print 'addout', repr(page), edge
            add_out(request.graphdata, [page, dst], linktype)

    for page in changed_new_in:
        for edge in changed_new_in[page]:
            #print 'addin', repr(page), edge
            linktype, src = edge
            add_in(request.graphdata, [src, page], linktype)

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
    request.graphdata.post_save(pagename)

def delete_moin_caches(request, pageitem):
    # Clear cache
    arena = PageEditor(request, pageitem.page_name)

    # delete pagelinks
    key = 'pagelinks'
    cache = caching.CacheEntry(request, arena, key, scope='item')
    cache.remove()

    # forget in-memory page text
    pageitem.set_raw_body(None)

    request.graphdata.cache = dict()

    # clean the cache
    for formatter_name in request.cfg.caching_formats:
        key = formatter_name
        cache = caching.CacheEntry(request, arena, key, scope='item')
        cache.remove()

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
    self.__dict__["_graphdata"].doing_rehash = _is_rehashing
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

    savegraphdata_execute(page.page_name, page.request, text, path, page)

def graphdata_copy(page, newpagename):
    text = page.get_raw_body()
    path = underlay_to_pages(page.request, page)

    savegraphdata_execute(newpagename, page.request, text, path, page)

# Note: PageEditor.renamePage seems to use .saveText for the new
# page (thus already updating the page's metas), so only the old page's
# metas need to be deleted explicitly.
def graphdata_rename(page):
    path = underlay_to_pages(page.request, page)

    # Rename is really filesystem-level rename, no old data is really
    # left behind, so it should be cleared.  When saving with text
    # 'deleted\n', no graph data is actually saved.
    savegraphdata_execute(page.page_name, page.request, 'deleted\n', path, page)

    # Rename might litter empty directories data/pagename and
    # data/pagename/cache, let's remove them
    oldpath = page.getPagePath(check_create=0)
    for dirpath, dirs, files in os.walk(oldpath, topdown=False):
        # If there are files left, some backups etc information is
        # still there, so let's quit
        if files:
            break

        os.rmdir(dirpath)
