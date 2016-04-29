# -*- coding: utf-8 -*-"
action_name = 'metaPackage'

import os
import zipfile
from datetime import datetime
from cStringIO import StringIO

from MoinMoin import wikiutil, user
from MoinMoin.Page import Page
from MoinMoin.packages import MOIN_PACKAGE_FILE, packLine
from MoinMoin.action.AttachFile import _get_files
from MoinMoin.action import AttachFile
from MoinMoin.metadata.query import get_metas, metatable_parseargs
from MoinMoin.metadata.util import log

from graphingwiki import values_to_form

def execute(pagename, request):
    pagename_header = '%s-%s.zip' % (pagename, datetime.now().isoformat()[:10])
    pagename_header = pagename_header.encode('ascii', 'ignore')
    
    request.content_type ='application/zip'
    request.headers['Content-Disposition'] = \
        'attachment; filename="%s"' % pagename_header

    args = values_to_form(request.values)

    try:
        args = args['args'][0]
    except (KeyError, IndexError):
        args = u''

    pagelist, metakeys, _ = metatable_parseargs(request, args, get_all_keys=True)

    renameDict = dict()

    for page in pagelist:
        metas = get_metas(request, page, ["gwikirename"], abs_attach=False, checkAccess=False)
        renameList = metas["gwikirename"]
        if renameList:
            renameDict[page] = renameList

    output = StringIO()
    zip = zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED)

    userid = user.getUserIdentification(request)
    script = [packLine(['MoinMoinPackage', '1']),]
    counter = 0

    for pagename in pagelist:
        counter += 1
        page = Page(request, pagename)
        timestamp = wikiutil.version2timestamp(page.mtime_usecs()) 
        # Underlay pages are in epoch 0, zipfile in python 2.7 does
        # not support this.
        if not timestamp:
            pagefile, rev, exists = page.get_rev()
            if rev == 99999999:
                # We should never get here
                log.error("Page %s neither in pages or underlay, skipping." % 
                          (pagename))
                continue
            timestamp = os.path.getctime(pagefile)
        pagetext = page.get_raw_body().encode("utf-8")
        filename = str(counter)
        zinfo = zipfile.ZipInfo(filename=filename, date_time=datetime.fromtimestamp(timestamp).timetuple()[:6])
        zinfo.compress_type = zipfile.ZIP_DEFLATED
        zip.writestr(zinfo, pagetext)

        targetNameList = renameDict.get(pagename, [pagename]) 
        for targetName in targetNameList:
            script.append(packLine(["AddRevision", filename, targetName, userid, ""]))

        for attachment in _get_files(request, pagename):
            counter += 1
            sourcefile = AttachFile.getFilename(request, pagename, attachment)
            filename = str(counter) + "-attachment"
            zip.write(sourcefile, filename) 
            script.append(packLine(["AddAttachment", filename, attachment, pagename, userid, ""]))
      
    zip.writestr(MOIN_PACKAGE_FILE, u"\n".join(script).encode("utf-8"))
    zip.close()

    request.write(output.getvalue())
