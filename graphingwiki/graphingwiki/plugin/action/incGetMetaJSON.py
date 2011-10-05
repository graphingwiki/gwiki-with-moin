# -*- coding: utf-8 -*-"
"""
    incGetMetaJSON action for graphingwiki

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

import MoinMoin.wikiutil as wikiutil

from graphingwiki import values_to_form

try:
    import simplejson as json
except ImportError:
    import json

def execute(pagename, request):
    request.content_type = "text/plain; charset=ascii"

    form = values_to_form(request.values)

    args = form.get('args', [None])[0]
    if not args:
        request.write('No data')
        return

    handle = form.get('handle', [None])[0]
    if handle:
        handle = str(handle)

    inc_get_metas = wikiutil.importPlugin(request.cfg, "xmlrpc", "IncGetMeta",
                                          "inc_get_metas")
    out = inc_get_metas(request, args, handle)
    json.dump(out, request, indent=2)

