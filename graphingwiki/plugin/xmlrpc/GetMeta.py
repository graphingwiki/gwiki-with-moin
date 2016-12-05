#! -*- coding: utf-8 -*-"
"""
    GetMeta xmlrpc plugin to MoinMoin/Graphingwiki
     - Sends the Metadata of desired pages

    @copyright: 2007 by Juhani Eronen <exec@iki.fi>
    @license: MIT <http://www.opensource.org/licenses/mit-license.php>
"""
from MoinMoin.metadata.query import metatable_parseargs, get_metas

#Used by action/metaCSV.py
def do_action(request, args, keysonly=True):
    # Expects MetaTable arguments
    pagelist, metakeys, _ = metatable_parseargs(request, args, 
                                                get_all_keys=True)
    # If we only want the keys as specified by the args
    if keysonly:
        return list(metakeys), list(pagelist)

    # Keys to the first row
    out = []
    out.append(metakeys)

    # Go through the pages, give list that has
    # the name of the page followed by the values of the keys
    for page in pagelist:
        # We're pretty sure the user has the read access to the pages,
        # so don't check again
        metas = get_metas(request, page, metakeys, checkAccess=False)
        row = [page]
        for key in metakeys:
            row.append([value for value in metas[key]])
        out.append(row)

    return out

def execute(xmlrpcobj, args, keysonly=True):
    request = xmlrpcobj.request
    _ = request.getText
    args = xmlrpcobj._instr(args)

    return do_action(request, args, keysonly)
