# -*- coding: utf-8 -*-

import re
from cStringIO import StringIO

from MoinMoin import config
from MoinMoin.Page import Page

try:
    import cairo
except ImportError:
    cairo = None


# Get action name for forms
def actionname(request, pagename=None):
    if not pagename:
        return request.page.url(request)
    else:
        return Page(request, pagename).url(request)


def id_escape(text):
    chr_re = re.compile('[^a-zA-Z0-9-_:.]')
    return chr_re.sub(lambda mo: '_%02x_' % ord(mo.group()), text)


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


def have_cairo():
    '''Returns true if cairo is imported successfully

    Checking whether cairo can be used should be done by actions and
    macros using this library.
    '''
    return cairo is not None


def cairo_surface_to_png(surface):
    stringio = StringIO()
    surface.write_to_png(stringio)
    surface.finish()
    return stringio.getvalue()
