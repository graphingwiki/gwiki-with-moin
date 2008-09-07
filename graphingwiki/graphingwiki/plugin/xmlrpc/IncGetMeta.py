"""
    Incremental GetMeta (prototype).

    @copyright: 2008 by Joachim Viide
    @license: MIT <http://www.opensource.org/licenses/mit-license.php>
"""

import os
import struct
import base64
import shelve
import xmlrpclib

from MoinMoin.formatter.text_plain import Formatter as TextFormatter
from graphingwiki.editing import getmetas, metatable_parseargs, decode_page

def diff(previous, current):
    removedPages = list()
    updates = dict()

    for page in set(previous) | set(current):
        currentPage = current.get(page, dict())
        prevPage = previous.get(page, dict())

        if page not in current:
            removedPages.append(page)
            continue

        for key in set(currentPage) | set(prevPage):
            currentValues = currentPage.get(key, set())
            prevValues = prevPage.get(key, set())

            added = list(currentValues - prevValues)
            discarded = list(prevValues - currentValues)

            if added or discarded:
                updates.setdefault(page, dict())[key] = added, discarded
            
    return removedPages, updates

def createNewHandle(db):
    number = db.get("", 0)
    db[""] = number + 1
    return base64.b64encode(struct.pack("!Q", number))

def getMetas(request, args, handle=None):
    data, pages, keys, _ = metatable_parseargs(request, args, get_all_keys=True)

    current = dict()
    for page in pages:
        # metatable_parseargs checks read permissions, no need to do it again
        metas = getmetas(request, data, page, keys, 
                         display=False, checkAccess=False)

        page = decode_page(page)
        current[page] = dict()
        for key in keys:
            values = set([value for (value, type) in metas[key]])
            current[page][decode_page(key)] = values

    path = os.path.join(request.cfg.data_dir, "getmetas.shelve")
    db = shelve.open(path)

    incremental = True
    try:
        if not handle or handle not in db:
            incremental = False
            handle = createNewHandle(db)
        previous = db.get(handle, dict())
        db[handle] = current
    finally:
        db.close()

    return [incremental, handle, diff(previous, current)]

def execute(xmlrpcobj, query, handle=None):
    request = xmlrpcobj.request
    request.formatter = TextFormatter(request)

    return getMetas(request, query, handle)
