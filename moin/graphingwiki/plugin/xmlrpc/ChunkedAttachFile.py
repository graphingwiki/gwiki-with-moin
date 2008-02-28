import os
import xmlrpclib
import md5

from tempfile import mkdtemp
from shutil import rmtree

from graphingwiki.editing import save_attachfile
from graphingwiki.editing import load_attachfile
from graphingwiki.editing import check_attachfile
from graphingwiki.editing import delete_attachfile

from graphingwiki.editing import list_attachments

CHUNK_SIZE = 1024 * 1024

def runChecked(func, request, pagename, filename, *args, **keys):
    # Checks ACLs and the return value of the called function.
    # If the return value is None, return Fault

    _ = request.getText
    if not request.user.may.read(pagename):
        return xmlrpclib.Fault(1, _("You are not allowed to access this page"))

    result = func(request, pagename, filename, *args, **keys)
    if result is None:
        return xmlrpclib.Fault(2, "%s: %s" % (_("Nonexisting attachment"),
                                              filename))

    return result

def info(request, pagename, filename):
    try:
        fpath, exists = check_attachfile(request, pagename, filename)
        if not exists:
            return None

        stream = open(fpath, "rb")
        digest = md5.new()

        data = stream.read(CHUNK_SIZE)
        while data:
            digest.update(data)
            data = stream.read(CHUNK_SIZE)

        digest = digest.hexdigest()
        size = stream.tell()
        stream.close()
    except:
        return None

    return [digest, size]

def load(request, pagename, filename, start, end):
    try:
        fpath, exists = check_attachfile(request, pagename, filename)
        if not exists:
            return None

        stream = open(fpath, "rb")
        stream.seek(start)
        data = stream.read(max(end-start, 0))
        stream.close()
    except:
        return None

    return xmlrpclib.Binary(data)

def reassembly(request, pagename, filename, chunkSize, digests, overwrite=True):
    _ = request.getText

    # Using the same access controls as in MoinMoin's xmlrpc_putPage
    # as defined in MoinMoin/wikirpc.py
    if (request.cfg.xmlrpc_putpage_trusted_only and
        not request.user.trusted):
        return xmlrpclib.Fault(1, _("You are not allowed to attach a "+
                                    "file to this page"))

    # Also check ACLs
    if not request.user.may.write(pagename):
        return xmlrpclib.Fault(1, _("You are not allowed to attach a "+
                                    "file to this page"))

    # Check whether the file already exists. If it does, check the hashes.
    fpath, exists = check_attachfile(request, pagename, filename)
    if chunkSize is not None and exists:
        try:
            stream = open(fpath, "rb")
        except:
            pass
        else:
            for digest in digests:
                data = stream.read(chunkSize)
                other = md5.new(data).hexdigest()
                if other != digest:
                    break
            else:
                data = stream.read(chunkSize)
                if not data:
                    stream.close()
                    return list()
            
            stream.close()

        # Fail if the file doesn't match and we don't want to overwrite.
        if overwrite:
            return xmlrpclib.Fault(2, _("Attachment not saved, file exists"))

    # If there are missing chunks, just return them.
    result = list_attachments(request, pagename)
    missing = [digest for digest in digests if digest not in result]
    if missing:
        return missing

    # Reassembly the file from the chunks into a temp file.
    tmpDir = mkdtemp()
    tmpPath = os.path.join(tmpDir, filename)
    try:
        tmp = file(tmpPath, 'wb')
    except:
        return xmlrpclib.Fault(3, _("Could not create temp file"))
    
    try:
        for bite in digests:
            data = load_attachfile(request, pagename, bite)
            if not data:
                return xmlrpclib.Fault(2, "%s: %s" % (_("Nonexisting "+
                                                        "attachment"),
                                                      filename))
            tmp.write(data)
    except:
        return xmlrpclib.Fault(3, _("Unknown error"))
    finally:
        tmp.close()

    # Attach the decoded file.
    success = save_attachfile(request, pagename, tmpPath, filename, overwrite)
    rmtree(tmpDir)

    # FIXME: What should we do when the cleanup fails?
    for bite in digests:
        delete_attachfile(request, pagename, bite)

    # On success signal that there were no missing chunks.
    if success is True:
        return list()
    
    if overwrite == False:
        return xmlrpclib.Fault(2, _("Attachment not saved, file exists"))

    return xmlrpclib.Fault(3, _("Unknown error while attaching file"))

def execute(xmlrpcobj, page, file, action='info', start=None, end=None):
    request = xmlrpcobj.request
    _ = request.getText

    page = xmlrpcobj._instr(page)

    if action == 'info':
        success = runChecked(info, request, page, file)
    elif action == 'load' and None not in (start, end):
        success = runChecked(load, request, page, file, start, end)
    elif action == 'reassembly' and start is not None:
        chunk, digests = start, end
        success = runChecked(reassembly, request, page, file, chunk, digests)
    else:
        success = xmlrpclib.Fault(3, _("No method specified or invalid span"))

    return map(unicode, success)
