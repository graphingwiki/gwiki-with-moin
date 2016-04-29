# -*- coding: utf-8 -*-

from MoinMoin import config

import sys
import os
import re
import socket
import xmlrpclib
from cStringIO import StringIO

# Get action name for forms
def actionname(request, pagename=None):
    if not pagename:
        return request.page.url(request)
    else:
        return Page(request, pagename).url(request)

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

def cairo_surface_to_png(surface):
    stringio = StringIO()
    surface.write_to_png(stringio)
    surface.finish()
    return stringio.getvalue()
