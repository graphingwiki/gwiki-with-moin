# -*- coding: utf-8 -*-

from MoinMoin import config

import sys
import os
import re
import socket
import xmlrpclib
from cStringIO import StringIO

SEPARATOR = '-gwikiseparator-'


# Get action name for forms
def actionname(request, pagename=None):
    if not pagename:
        return request.page.url(request)
    else:
        return Page(request, pagename).url(request)

def url_escape(text):
    # Escape characters that break links in html values fields, 
    # macros and urls with parameters
    return re.sub('[\]"\?#&+]', lambda mo: '%%%02x' % ord(mo.group()), text)

def url_unescape(text):
    return re.sub(r"%([0-9a-f]{2})", lambda mo: chr(int(mo.group(1), 16)), text)

def id_escape(text):
    chr_re = re.compile('[^a-zA-Z0-9-_:.]')
    return chr_re.sub(lambda mo: '_%02x_' % ord(mo.group()), text)

def id_unescape(text):
    chr_re = re.compile('_([0-9a-f]{2})_')
    return chr_re.sub(lambda mo: chr(int(mo.group(1), 16)), text)

def values_to_form(values):
    # Form keys are not unicode for some reason
    oldform = values.to_dict(flat=False)
    newform = dict()
    for key in oldform:
        if not isinstance(key, unicode):
            newkey = unicode(key, config.charset)
        else:
            newkey = key
        newform[newkey] = oldform[key]
    return newform

# Finding dependencies centrally

pil_found = False
pil_image = None

try:
    from PIL import Image as pil_image
    pil_found = True
except ImportError:
    pass

gv_found = True
gv = None

try:
    import gv
except ImportError:
    try:
        sys.path.append('/usr/lib/graphviz/python')
        sys.path.append('/usr/local/lib/graphviz/python') # OSX
        sys.path.append('/usr/lib/pyshared/python2.6') # Ubuntu 9.10
        sys.path.append('/usr/lib/pyshared/python2.5') # Ubuntu 9.10
        import gv
    except ImportError:
        sys.path[-1] = '/usr/lib64/graphviz/python'
        try:
            import gv
        except ImportError:
            gv_found = False

igraph_found = True
igraph = None

try:
    import igraph
except ImportError:
    igraph_found = False
    pass

if gv_found:
    # gv needs libag to be initialised before using any read methods,
    # making a graph here seems to ensure aginit() is called
    gv.graph(' ')

cairo_found = True
cairo = None

try:
    import cairo
except ImportError:
    cairo_found = False
    pass

geoip_found = True
GeoIP = None

try:
    import GeoIP
except ImportError:
    geoip_found = False
    pass

# Helper functions for dealing with underlays.

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
    from graphingwiki.backend.shelvedb import GraphData
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

def _get_save_plugin(self):
    from graphingwiki.plugin.action.savegraphdata import execute as graphsaver
    return graphsaver

## TODO: Hook PageEditor.sendEditor to add data on template to the
## text of the saved page?

def graphdata_save(self):
    graphsaver = _get_save_plugin(self)

    if not graphsaver:
        return

    path = underlay_to_pages(self.request, self)
    text = self.get_raw_body()

    graphsaver(self.page_name, self.request, text, path, self)

def graphdata_copy(self, newpagename):
    graphsaver = _get_save_plugin(self)

    if not graphsaver:
        return

    text = self.get_raw_body()
    path = underlay_to_pages(self.request, self)

    graphsaver(newpagename, self.request, text, path, self)

def graphdata_rename(self):
    graphsaver = _get_save_plugin(self)
    path = underlay_to_pages(self.request, self)

    # Rename is really filesystem-level rename, no old data is really
    # left behind, so it should be cleared.  When saving with text
    # 'deleted\n', no graph data is actually saved.
    graphsaver(self.page_name, self.request, 'deleted\n', path, self)

    # Rename might litter empty directories data/pagename and
    # data/pagename/cache, let's remove them
    oldpath = self.getPagePath(check_create=0)
    for dirpath, dirs, files in os.walk(oldpath, topdown=False):
        # If there are files left, some backups etc information is
        # still there, so let's quit
        if files:
            break

        os.rmdir(dirpath)

def install_hooks(*args, **keys):
    pass

def cairo_surface_to_png(surface):
    stringio = StringIO()
    surface.write_to_png(stringio)
    surface.finish()
    return stringio.getvalue()
