# -*- coding: utf-8 -*-"
"""
    MetaSearch action to MoinMoin
     - Searching pages with certain metadata keys or values

    @copyright: 2007 by Juhani Eronen <exec@iki.fi>
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
import re

from urllib import unquote as url_unquote
from urllib import quote as url_quote

from MoinMoin import wikiutil
from MoinMoin import config
from MoinMoin.formatter.text_html import Formatter as HtmlFormatter

from graphingwiki.patterns import encode
from graphingwiki.patterns import GraphData

regexp_re = re.compile('^/.+/$')

def elemlist(request, formatter, elems, text):
    _ = request.getText
    if not elems:
        return
    request.write(formatter.paragraph(1))
    request.write(formatter.text(_("The following") + " %s " % text
                                 + _("found")))
    request.write(formatter.paragraph(0))
    request.write(formatter.bullet_list(1))
    for elem in sorted(elems):
        kwelem = {'querystr': 'action=MetaSearch&q=' + elem,
                 'allowed_attrs': ['title', 'href', 'class'],
                 'class': 'meta_search'}
        request.write(formatter.listitem(1))
        request.write(formatter.pagelink(1, request.page.page_name,
                                         request.page, **kwelem))
        request.write(formatter.text(elem))
        request.write(formatter.pagelink(0))
        request.write(formatter.listitem(0))
    request.write(formatter.bullet_list(0))

def execute(pagename, request):
    request.http_headers()
    _ = request.getText


    # This action generate data using the user language
    request.setContentLanguage(request.lang)

    wikiutil.send_title(request, request.getText('Search by metadata'),
                        pagename=pagename)

    # Start content - IMPORTANT - without content div, there is no
    # direction support!
    if not hasattr(request, 'formatter'):
        formatter = HtmlFormatter(request)
    else:
        formatter = request.formatter
    request.page.formatter = formatter

    request.write(formatter.startContent("content"))

    q = ''
    if request.form.has_key('q'):
        q = ''.join(request.form['q'])

    pagename = '../' * pagename.count('/') + pagename

    request.write(u'<form method="GET" action="%s">\n' % pagename)
    request.write(u'<input type=hidden name=action value="%s">' %
                  ''.join(request.form['action']))

    request.write(u'<input type="text" name="q" size=50 value="%s">' % q)
    request.write(u'<input type=submit value="' + _('Search') +
                  '">' + u'\n</form>\n')

    if q:
        if regexp_re.match(q):
            try:
                page_re = re.compile("%s" % q[1:-1])
                q = ''
            except:
                request.write(formatter.paragraph(1))
                request.write(formatter.text(_("Bad regexp!")))
                request.write(formatter.paragraph(0))

                # End content
                request.write(formatter.endContent()) # end content div
                # Footer
                wikiutil.send_footer(request, pagename)
                
        graphdata = GraphData(request)
        graphdata.reverse_meta()
        globaldata = graphdata.globaldata
        keys_on_pages = graphdata.keys_on_pages
        vals_on_pages = graphdata.vals_on_pages

        keyhits = set([])
        keys = set([])
        for key in keys_on_pages:
            if q:
                if key == url_quote(encode(q)):
                    keyhits.update(keys_on_pages[key])
                    keys.add(unicode(url_unquote(key), config.charset))
            else:
                if page_re.match(unicode(url_unquote(key), config.charset)):
                    keyhits.update(keys_on_pages[key])
                    keys.add(unicode(url_unquote(key), config.charset))

        valhits = set([])
        vals = set([])
        for val in vals_on_pages:
            if q:
                if val == encode(q):
                    valhits.update(vals_on_pages[val])
                    vals.add(unicode(val, config.charset))
            else:
                if page_re.match(unicode(val, config.charset)):
                    valhits.update(vals_on_pages[val])
                    vals.add(unicode(val, config.charset))

        if not q:
            elemlist(request, formatter, keys, _('keys'))
            elemlist(request, formatter, vals, _('values'))

        request.write(formatter.paragraph(1))
        request.write(formatter.text(_("Found as key in following pages")))
        request.write(formatter.paragraph(0))

        request.write(formatter.bullet_list(1))
        for page in sorted(keyhits):
            page = unicode(url_unquote(page), config.charset)
            request.write(formatter.listitem(1))
            request.write(formatter.pagelink(1, page))
            request.write(formatter.text(page))
            request.write(formatter.pagelink(0))
            request.write(formatter.listitem(0))
                         
        request.write(formatter.bullet_list(0))

        request.write(formatter.paragraph(1))
        request.write(formatter.text(_("Found as value in following pages")))
        request.write(formatter.paragraph(0))
        request.write(formatter.bullet_list(1))
        for page in sorted(valhits):
            page = unicode(url_unquote(page), config.charset)
            request.write(formatter.listitem(1))
            request.write(formatter.pagelink(1, page))
            request.write(formatter.text(page))
            request.write(formatter.pagelink(0))
            request.write(formatter.listitem(0))
                         
        request.write(formatter.bullet_list(0))

        graphdata.closedb()

    # End content
    request.write(formatter.endContent()) # end content div

    # Footer
    wikiutil.send_footer(request, pagename)
