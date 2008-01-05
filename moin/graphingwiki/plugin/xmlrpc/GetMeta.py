#! -*- coding: utf-8 -*-"
"""
    GetMeta xmlrpc plugin to MoinMoin/Graphingwiki
     - Sends the Metadata of desired pages

    @copyright: 2007 by Juhani Eronen <exec@iki.fi>
    @license: MIT <http://www.opensource.org/licenses/mit-license.php>
"""
import urllib
 
from graphingwiki.editing import metatable_parseargs, getmetas

def execute(xmlrpcobj, args, keysonly=True):
    request = xmlrpcobj.request
    _ = request.getText

    # Expects MetaTable arguments
    globaldata, pagelist, metakeys = metatable_parseargs(request, args,
                                                         get_all_keys=True)


    # If we only want the keys as specified by the args
    if keysonly:
        globaldata.closedb()
        return list(metakeys), list(pagelist)

    # Keys to the first row
    out = []
    out.append(metakeys)

    # Go through the pages, give list that has
    # the name of the page followed by the values of the keys
    for page, metas in getmetas(request, globaldata, pagelist, metakeys):
        row = [page]
        for key in metakeys:
            row.append([value for (value, type) in metas[key]])
        out.append(row)
    
    # Close db, get out
    globaldata.closedb()

    return out
