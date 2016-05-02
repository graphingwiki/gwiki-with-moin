# -*- coding: utf-8 -*-"
"""
    MetaRadarDiagram macro plugin to MoinMoin
     - Makes links to the action that provides for the images

    @copyright: 2008 by Juhani Eronen <exec@iki.fi>
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
import StringIO

from MoinMoin.macro.Include import _sysmsg
from MoinMoin.metadata.query import get_metas, metatable_parseargs, ordervalue

from graphingwiki import have_cairo
from graphingwiki.util import url_construct

from MetaRadarChart import radarchart_args

Dependencies = ['metadata']

MAX_WIDTH = 1000

def execute(macro, args):
    formatter = macro.formatter
    macro.request.page.formatter = formatter
    request = macro.request
    _ = request.getText

    if not have_cairo():
        return _sysmsg % ('error', _(\
                "ERROR: Cairo Python extensions not installed. " +\
                    "Not performing layout."))

    url_args, args = radarchart_args(args)

    # For multiple radar charts per table row
    try:
        height = ''.join(url_args.get('height', list()))
        width = ''.join(url_args.get('width', list()))
        if not height: 
            height = MAX_WIDTH
        if not width:
            width = MAX_WIDTH
        height, width = int(height), int(width)
    except ValueError:
        pass

    # MAX_WIDTH is the assumed max_width here
    amount = MAX_WIDTH / min(height, width)
    if amount < 1:
        amount = 1

    # Note, metatable_parseargs deals with permissions
    pagelist, metakeys, _ = metatable_parseargs(request, args,
                                                get_all_keys=True)

    values = set()
    for page in pagelist:
        metas = get_metas(request, page, metakeys)
        for key in metas:
            # Get the maximum value of each key on a page
            if metas[key]:
                numberedvals = dict()
                for i, val in enumerate(map(ordervalue, metas[key])):
                    numberedvals[val] = i
                maxval = max(numberedvals.keys())
                i = numberedvals[maxval]
                # This contraption is here because we need to deliver
                # unparsed (textual) values in urls
                values.add(metas[key][i])
    for val in values:
        if val.startswith('attachment'):
            # A bit ugly fix for a weird corner case
            val = "attachment:%s" % (val[11:])
        url_args.setdefault('value', list()).append(val)

    out = StringIO.StringIO()
    out.write(macro.formatter.linebreak() +
              u'<div class="metaradartable">' +
              macro.formatter.table(1))

    rowcount = (len(pagelist) / amount)
    if len(pagelist) % amount:
        rowcount += 1
    # Iterate over the number of rows
    for i in range(rowcount):

        out.write(macro.formatter.table_row(1))

        pages = pagelist[i*amount:(i+1)*amount]

        # First enter page names to first row
        for page in pages:
            out.write(macro.formatter.table_cell(1, {'class': 'meta_page'}))
            out.write(macro.formatter.pagelink(1, page))
            out.write(macro.formatter.text(page))
            out.write(macro.formatter.pagelink(0))
            out.write(macro.formatter.linebreak())
        # Don't make extra squares for the first row
        if i:
            for j in range(amount - len(pages)):
                out.write(macro.formatter.table_cell(1))

        out.write(macro.formatter.table_row(1))

        # Chart images to the other row
        for page in pages:
            out.write(macro.formatter.table_cell(1, {'class': 'meta_radar'}))
            out.write(u'<img src="%s">' % 
                      (url_construct(request, url_args, page)))
            out.write(macro.formatter.linebreak())
        if i:
            for j in range(amount - len(pages)):
                out.write(macro.formatter.table_cell(1))

    out.write(macro.formatter.table(0) + u'</div>')

    return out.getvalue()
