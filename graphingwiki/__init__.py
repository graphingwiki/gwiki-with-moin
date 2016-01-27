# -*- coding: utf-8 -*-

import MoinMoin.wsgiapp
import MoinMoin.wikisync  
import MoinMoin.wikiutil as wikiutil
import MoinMoin.web.contexts
import MoinMoin.xmlrpc

from MoinMoin import config
from MoinMoin.Page import Page
from MoinMoin.PageEditor import PageEditor
from MoinMoin.action import AttachFile
from MoinMoin.wikiutil import importPlugin, PluginMissingError
from MoinMoin.security import ACLStringIterator
from MoinMoin.script import MoinScript
from MoinMoin.web.request import Request
from MoinMoin.web.contexts import ScriptContext

import sys
import os
import re
import socket
import xmlrpclib
from cStringIO import StringIO

def RequestCLI(pagename='', parse=True):
    """
    The MoinScript class does command line argument parsing, which
    might not be what is desired, as it will complain about custom
    arguments in gwiki-* scripts. MoinScript initialises the request
    by calling up ScriptContext, which is then assigned to the
    script.request.

    If a gwiki-* script uses non-MoinScript command line arguments,
    the ScriptContext is initialized with minimum sane default.
    """
    if parse:
        script = MoinScript()
        if pagename:
            script.parser.set_defaults(page=pagename)
        script.options, script.args = script.parser.parse_args()
        script.init_request()
        return script.request

    # Default values
    return ScriptContext(None, pagename)

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

# HTTP Auth support to wikisync:
# http://moinmo.in/FeatureRequests/WikiSyncWithHttpAuth
class MoinRemoteWikiHttpAuth(MoinMoin.wikisync.MoinRemoteWiki):
    """ Used for MoinMoin wikis reachable via XMLRPC. """
    def __init__(self, request, interwikiname, prefix, pagelist, user, password, verbose=False):
        self.request = request
        self.prefix = prefix
        self.pagelist = pagelist
        self.verbose = verbose
        _ = self.request.getText

        wikitag, wikiurl, wikitail, wikitag_bad = wikiutil.resolve_interwiki(self.request, interwikiname, '')
        self.wiki_url = wikiutil.mapURL(self.request, wikiurl)
        self.valid = not wikitag_bad
        self.xmlrpc_url = self.wiki_url + "?action=xmlrpc2"
        if not self.valid:
            self.connection = None
            return

        httpauth = False
        notallowed = _("Invalid username or password.")

        self.connection = self.createConnection()

        try:
            iw_list = self.connection.interwikiName()
        except socket.error:
            raise MoinMoin.wikisync.UnsupportedWikiException(_("The wiki is currently not reachable."))
        except xmlrpclib.Fault, err:
            raise MoinMoin.wikisync.UnsupportedWikiException("xmlrpclib.Fault: %s" % str(err))
        except xmlrpclib.ProtocolError, err:
            if err.errmsg != "Authorization Required":
                raise

            if user and password:
                try:
                    import urlparse
                    import urllib

                    def urlQuote(string):
                        if isinstance(string, unicode):
                            string = string.encode("utf-8")
                        return urllib.quote(string, "/:")

                    scheme, netloc, path, a, b, c = \
                        urlparse.urlparse(self.wiki_url)
                    action = "action=xmlrpc2"

                    user, password = map(urlQuote, [user, password])
                    netloc = "%s:%s@%s" % (user, password, netloc)
                    self.xmlrpc_url = urlparse.urlunparse((scheme, netloc, 
                                                           path, "", 
                                                           action, ""))

                    self.connection = self.createConnection()
                    iw_list = self.connection.interwikiName()

                    httpauth = True
                except:
                    raise MoinMoin.wikisync.NotAllowedException(notallowed)
            elif user:
                return
            else:
                raise MoinMoin.wikisync.NotAllowedException(notallowed)

        if user and password:
            token = self.connection.getAuthToken(user, password)
            if token:
                self.token = token
            elif httpauth:
                self.token = None
            else:
                raise MoinMoin.wikisync.NotAllowedException(_("Invalid username or password."))
        else:
            self.token = None

        self.remote_interwikiname = remote_interwikiname = iw_list[0]
        self.remote_iwid = remote_iwid = iw_list[1]
        self.is_anonymous = remote_interwikiname is None
        if not self.is_anonymous and interwikiname != remote_interwikiname:
            raise MoinMoin.wikisync.UnsupportedWikiException(_("The remote wiki uses a different InterWiki name (%(remotename)s)"
                                             " internally than you specified (%(localname)s).") % {
                "remotename": wikiutil.escape(remote_interwikiname), "localname": wikiutil.escape(interwikiname)})

        if self.is_anonymous:
            self.iwid_full = MoinMoin.wikisync.packLine([remote_iwid])
        else:
            self.iwid_full = MoinMoin.wikisync.packLine([remote_iwid, 
                                                         interwikiname])

MoinMoin.wikisync.MoinRemoteWiki = MoinRemoteWikiHttpAuth

# Main function for injecting graphingwiki extensions straight into
# Moin's beating heart.

_hooks_installed = False

def install_hooks(rehashing=False):
    global _hooks_installed, _is_rehashing
    if _hooks_installed:
        return
    _is_rehashing = rehashing

    _hooks_installed = True


def cairo_surface_to_png(surface):
    stringio = StringIO()
    surface.write_to_png(stringio)
    surface.finish()
    return stringio.getvalue()
