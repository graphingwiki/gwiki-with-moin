# -*- coding: utf-8 -*-

"""
Shelve backend for gwiki

This is the original gwiki backend. It's slow, it occasionally
corrupts itself and it's pessimal at concurrency (uses a lock file).
Needless to say, it doesn't do ACID.

"""
import shelve
import random
import errno
import fcntl
import os

from basedb import GraphDataBase
from MoinMoin.metadata.util import (encode_page, decode_page, node_type,
                                    log, NO_TYPE, SPECIAL_ATTRS)

from time import time, sleep

class LockTimeout(Exception):
    pass

class _Lock(object):
    CHECK_INTERVAL = 0.05

    def __init__(self, lock_path, exclusive=False):
        self._lock_path = lock_path
        self._exclusive = exclusive
        self._fd = None

    def is_locked(self):
        return self._fd is not None

    def acquire(self, timeout=None):
        if self._fd is not None:
            return

        if timeout is not None:
            expires = time() + timeout
        else:
            expires = None

        fd = None
        try:
            while True:
                if fd is None:
                    fd = os.open(self._lock_path, os.O_CREAT | os.O_RDWR)

                if fd is not None:
                    mode = fcntl.LOCK_SH
                    if self._exclusive:
                        mode = fcntl.LOCK_EX

                    try:
                        fcntl.lockf(fd, mode | fcntl.LOCK_NB)
                    except IOError, error:
                        if error.errno not in (errno.EAGAIN, errno.EACCES):
                            raise
                    else:
                        break

                timeout = self.CHECK_INTERVAL
                if expires is not None:
                    remaining = expires - time()
                    remaining -= 0.5 * remaining * random.random()
                    timeout = min(timeout, remaining)
                if timeout <= 0:
                    raise LockTimeout()
                sleep(timeout)
        except:
            if fd is not None:
                fcntl.lockf(fd, fcntl.LOCK_UN)
                os.close(fd)
            raise

        self._fd = fd

    def release(self):
        if self._fd is None:
            return False

        fcntl.lockf(self._fd, fcntl.LOCK_UN)
        os.close(self._fd)
        self._fd = None
        return True

class GraphData(GraphDataBase):
    is_acid = False

    UNDEFINED = object()

    def __init__(self, request, **kw):
        log.debug("shelve graphdb init")
        GraphDataBase.__init__(self, request, **kw)

        gddir = os.path.join(request.cfg.data_dir, 'graphdata')
        if not os.path.isdir(gddir):
            os.mkdir(gddir)
        self.graphshelve = os.path.join(gddir, 'graphdata.shelve')

        self.use_sq_dict = getattr(request.cfg, 'use_sq_dict', False)
        if self.use_sq_dict:
            import sq_dict
            self.shelveopen = sq_dict.shelve
        else:
            self.shelveopen = shelve.open

        # XXX (falsely) assumes shelve.open creates file with same name;
        # it happens to work with the bsddb backend.
        if not os.path.exists(self.graphshelve):
            db = self.shelveopen(self.graphshelve, 'c')
            db.close()

        self.db = None
        self.cache = dict()
        self.out = dict()

        lock_path = os.path.join(gddir, "graphdata-lock")
        self._lock_timeout = getattr(request.cfg, 'graphdata_lock_timeout', None)
        self._readlock = _Lock(lock_path, exclusive=False)
        self._writelock = _Lock(lock_path, exclusive=True)

    def __getitem__(self, item):
        page = encode_page(item)

        if page in self.out:
            if self.out[page] is self.UNDEFINED:
                raise KeyError(page)
            return self.out[page]

        if page in self.cache:
            return self.cache[page]

        self.readlock()
        self.cache[page] = self.db[page]
        return self.cache[page]

    def __setitem__(self, item, value):
        self.savepage(item, value)

    def savepage(self, pagename, pagedict):
        log.debug("savepage %s = %s" % (repr(pagename), repr(pagedict)))
        page = encode_page(pagename)

        self.out[page] = pagedict
        self.cache.pop(page, None)

    def is_saved(self, pagename):
        return self.getpage(pagename).get('saved', False)

    def get_out(self, pagename):
        return self.getpage(pagename).get(u'out', {})

    def get_in(self, pagename):
        return self.getpage(pagename).get(u'in', {})

    def get_meta(self, pagename):
        return self.getpage(pagename).get(u'meta', {})

    def get_metakeys(self, name):
        """
        Return the complete set of page's (non-link) meta keys, plus gwiki category.
        """

        page = self.getpage(name)
        keys = set(page.get('meta', dict()))

        if page.get('out', dict()).has_key('gwikicategory'):
            keys.add('gwikicategory')

        return keys

    def pagenames(self):
        return self.iterkeys()

    def cacheset(self, item, value):
        page = encode_page(item)

        self.cache[page] = value

    def __delitem__(self, item):
        self.delpage(item)

    def delpage(self, pagename):
        log.debug("delpage %s" % (repr(pagename),))
        page = encode_page(pagename)

        self.out[page] = self.UNDEFINED
        self.cache.pop(page, None)

    def __iter__(self):
        self.readlock()

        for key in self.db.keys():
            if self.out.get(key, None) is self.UNDEFINED:
                continue
            yield decode_page(key)

    def keys(self):
        return list(self.__iter__())

    def __contains__(self, item):
        page = encode_page(item)

        if page in self.out:
            return self.out[page] is not self.UNDEFINED

        if page in self.cache:
            return True

        self.readlock()
        return page in self.db

    def set_page_meta(self, pagename, newmeta):
        pagedata = self.getpage(pagename)
        pagedata[u'meta'] = newmeta
        self.savepage(pagename, pagedata)

    def set_acl(self, pagename, acl):
        pagedata = self.getpage(pagename)
        pagedata[u'acl'] = acl
        self.savepage(pagename, pagedata)

    def set_saved(self, pagename, saved, mtime):
        pagedata = self.getpage(pagename)
        pagedata[u'mtime'] = mtime
        pagedata[u'saved'] = saved
        self.savepage(pagename, pagedata)

    def clear_page(self, pagename):
        if self.get_in(pagename):
            pagedata = self.getpage(pagename)
            pagedata[u'saved'] = False
            pagedata[u'meta'] = dict()
            pagedata[u'out'] = dict()
            self.savepage(pagename, pagedata)
        else:
            self.delpage(pagename)

    def readlock(self):
        if self._writelock.is_locked():
            return
        if self._readlock.is_locked():
            return

        log.debug("getting a read lock for %r" % (self.graphshelve,))
        try:
            self._readlock.acquire(self._lock_timeout)
        except LockTimeout:
            items = self.graphshelve, self._lock_timeout
            log.error("getting a read lock for %r timed out after %.02fs" % items)
            raise
        log.debug("got a read lock for %r" % (self.graphshelve,))

        self.db = self.shelveopen(self.graphshelve, "r")

    def writelock(self):
        if self._writelock.is_locked():
            return

        if self._readlock.is_locked():
            if self.db is not None:
                self.db.close()
                self.db = None
            self._readlock.release()
            log.debug("released a write lock for %r" % (self.graphshelve,))

        log.debug("getting a write lock for %r" % (self.graphshelve,))
        try:
            self._writelock.acquire(self._lock_timeout)
        except LockTimeout:
            items = self.graphshelve, self._lock_timeout
            log.error("getting a write lock for %r timed out after %.02fs" % items)
            raise
        log.debug("got a write lock for %r" % (self.graphshelve,))

        self.db = self.shelveopen(self.graphshelve, "c")

    def close(self):
        if self.out:
            self.writelock()

            for key, value in self.out.items():
                if value is self.UNDEFINED:
                    self.db.pop(key, None)
                else:
                    self.db[key] = value

            self.out = dict()

        self.cache.clear()

        if self.db is not None:
            self.db.close()
            self.db = None

        if self._writelock.release():
            log.debug("released a write lock for %r" % (self.graphshelve,))
        else:
            log.debug("did not release any write locks for %r" % (self.graphshelve,))

        if self._readlock.release():
            log.debug("released a read lock for %r" % (self.graphshelve,))
        else:
            log.debug("did not released any read locks for %r" % (self.graphshelve,))

    def set_page(self, request, pagename, new_data):
        # Get a copy of current data
        old_outs = self.get_out(pagename)

        changed_new_out, changed_del_out, changed_new_in, changed_del_in = \
            self._changed_meta(request, pagename, old_outs, new_data)

        # Insert metas and other stuff from parsed content
        cur_time = time()

        self.set_page_meta(pagename, new_data.get(pagename, dict()).get(u'meta', dict()))
        self.set_acl(pagename, new_data.get(pagename, dict()).get(u'acl', ''))
        self.set_saved(pagename, True, cur_time)

        self._change_links(changed_new_out, changed_del_out, changed_new_in, changed_del_in)

    def _changed_meta(self, request, pagename, old_outs, new_data):
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

    def _change_links(self, changed_new_out, changed_del_out, changed_new_in, changed_del_in):
        # Save the links that have truly changed
        for page in changed_del_out:
            for edge in changed_del_out[page]:
                #print 'delout', repr(page), edge
                linktype, dst = edge
                self.__remove_out([page, dst], [linktype])

        for page in changed_del_in:
            for edge in changed_del_in[page]:
                #print 'delin', repr(page), edge
                linktype, src = edge
                self.__remove_in([src, page], [linktype])

        for page in changed_new_out:
            for i, edge in enumerate(changed_new_out[page]):
                linktype, dst = edge
                #print 'addout', repr(page), edge
                self._add_out([page, dst], linktype)

        for page in changed_new_in:
            for edge in changed_new_in[page]:
                #print 'addin', repr(page), edge
                linktype, src = edge
                self._add_in([src, page], linktype)

    def _remove_in(self, (frm, to), linktype):
        "Remove in-links from local nodes to current node"

        temp = self.getpage(to)
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
        self[to] = temp

    def _remove_out(self, (frm, to), linktype):
        "remove outlinks"

        temp = self.get(frm, {})

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

        self[frm] = temp

    def _add_in(self, (frm, to), linktype):
        "Add in-links from current node to local nodes"

        if not linktype:
            linktype = NO_TYPE

        temp = self.get(to, {})

        if not temp.has_key(u'in'):
            temp[u'in'] = {linktype: [frm]}
        elif not temp[u'in'].has_key(linktype):
            temp[u'in'][linktype] = [frm]
        else:
            temp[u'in'][linktype].append(frm)

        # Notification that the destination has changed
        temp[u'mtime'] = time()

        self[to] = temp

    def _add_out(self, (frm, to), linktype):
        "Add out-links from local nodes to current node"

        if not linktype:
            linktype = NO_TYPE

        temp = self.get(frm, {})

        if not temp.has_key(u'out'):
            temp[u'out'] = {linktype: [to]}
        elif not temp[u'out'].has_key(linktype):
            temp[u'out'][linktype] = [to]
        else:
            temp[u'out'][linktype].append(to)

        self[frm] = temp

    def _add_link(self, pagename, nodename, linktype):
        edge = [pagename, nodename]

        self._add_in(edge, linktype)
        self._add_out(edge, linktype)

    def commit(self):
        # Ha, puny gullible humans think I do transactions
        pass

    abort = commit

