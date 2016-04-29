# -*- coding: utf-8 -*-"
"""
    LinkedIn macro plugin to MoinMoin/Graphingwiki
     - Shows pages in which the current page has been linked in

    @copyright: 2006 by Juhani Eronen <exec@iki.fi>
    @license: MIT <http://www.opensource.org/licenses/mit-license.php>

    Permission is hereby granted, free of charge, to any person
    obtaining a copy of this software and associated documentation
    files (the "Software"), to deal in the Software without
    restriction, including without limitation the rights to use, copy,
    modify, merge, publish, distribute, sublicense, and/or sell copies
    of the Software, and to permit persons to whom the Software is
    furnished to do so, subject to the following conditions:

    The above copyright notice and this permission notice shall be
    included in all copies or substantial portions of the Software.

    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
    EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
    MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
    NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
    HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
    WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
    OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
    DEALINGS IN THE SOFTWARE.

"""
from MoinMoin.metadata.constants import NO_TYPE

Dependencies = ['pagelinks']


def nodes(request, pagename, meta):
    formatter = request.formatter
    out = []
    nodes = set()
    # User rights are not checked here as the page will not be
    # displayed at all if user does not have rights

    page_in = request.graphdata.get_in(pagename)

    for type in page_in:
        for page in page_in[type]:

            # User rights _ARE_ checked here!
            if not request.user.may.read(page):
                continue

            typeinfo = ''
            if meta and type != NO_TYPE:
                typeinfo = " (%s)" % (type)
            if page not in nodes:
                out.append(formatter.pagelink(1, page) +
                           formatter.text(page + typeinfo) +
                           formatter.pagelink(0, page))
                nodes.add(page)
    return out


def execute(macro, args):
    pagename = macro.formatter.page.page_name
    request = macro.request
    _ = request.getText

    meta = False
    if args and 'meta' in args:
        meta = True

    out = nodes(request, pagename, meta)

    # linebreak's knowledge of being in a preformatted area sucks
    return "%s: " % _("Linked in pages") + ', '.join(out) + \
           macro.formatter.linebreak(preformatted=0)
