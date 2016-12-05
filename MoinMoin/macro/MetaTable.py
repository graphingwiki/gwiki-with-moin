# -*- coding: utf-8 -*-"
"""
    MetaTable macro plugin to MoinMoin/Graphingwiki
     - Shows in tabular form the Metadata of desired pages

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
from urllib import quote

from MoinMoin.Page import Page
from MoinMoin.parser.text_moin_wiki import Parser
from MoinMoin.wikiutil import form_writer

from MoinMoin.metadata.constants import PROPERTIES
from MoinMoin.metadata.util import url_escape
from MoinMoin.metadata.query import (metatable_parseargs, get_metas,
                                     get_properties, add_matching_redirs)
from MoinMoin.metadata.wikitextutil import format_wikitext

try:
    import simplejson as json
except ImportError:
    import json

Dependencies = ['metadata']

# SVG color scheme
COLORS = ['aliceblue', 'antiquewhite', 'aqua', 'aquamarine',
          'azure', 'beige', 'bisque', 'black', 'blanchedalmond',
          'blue', 'blueviolet', 'brown', 'burlywood', 'cadetblue',
          'chartreuse', 'chocolate', 'coral', 'cornflowerblue',
          'cornsilk', 'crimson', 'cyan', 'darkblue', 'darkcyan',
          'darkgoldenrod', 'darkgray', 'darkgreen', 'darkgrey',
          'darkkhaki', 'darkmagenta', 'darkolivegreen', 'darkorange',
          'darkorchid', 'darkred', 'darksalmon', 'darkseagreen',
          'darkslateblue', 'darkslategray', 'darkslategrey',
          'darkturquoise', 'darkviolet', 'deeppink', 'deepskyblue',
          'dimgray', 'dimgrey', 'dodgerblue', 'firebrick', 'floralwhite',
          'forestgreen', 'fuchsia', 'gainsboro', 'ghostwhite', 'gold',
          'goldenrod', 'gray', 'grey', 'green', 'greenyellow', 'honeydew',
          'hotpink', 'indianred', 'indigo', 'ivory', 'khaki', 'lavender',
          'lavenderblush', 'lawngreen', 'lemonchiffon', 'lightblue',
          'lightcoral', 'lightcyan', 'lightgoldenrodyellow', 'lightgray',
          'lightgreen', 'lightgrey', 'lightpink', 'lightsalmon',
          'lightseagreen', 'lightskyblue', 'lightslategray', 'lightslategrey',
          'lightsteelblue', 'lightyellow', 'lime', 'limegreen', 'linen',
          'magenta', 'maroon', 'mediumaquamarine', 'mediumblue',
          'mediumorchid', 'mediumpurple', 'mediumseagreen', 'mediumslateblue',
          'mediumspringgreen', 'mediumturquoise', 'mediumvioletred',
          'midnightblue', 'mintcream', 'mistyrose', 'moccasin', 'navajowhite',
          'navy', 'oldlace', 'olive', 'olivedrab', 'orange', 'orangered',
          'orchid', 'palegoldenrod', 'palegreen', 'paleturquoise',
          'palevioletred', 'papayawhip', 'peachpuff', 'peru', 'pink',
          'plum', 'powderblue', 'purple', 'red', 'rosybrown', 'royalblue',
          'saddlebrown', 'salmon', 'sandybrown', 'seagreen', 'seashell',
          'sienna', 'silver', 'skyblue', 'slateblue', 'slategray',
          'slategrey', 'snow', 'springgreen', 'steelblue', 'tan', 'teal',
          'thistle', 'tomato', 'turquoise', 'violet', 'wheat', 'white',
          'whitesmoke', 'yellow', 'yellowgreen']


def wrap_span(request, pageobj, key, data, id):
    pagename = pageobj.page_name
    fdata = format_wikitext(request, data)

    if not key:
        return fdata

    header = False

    if key == data:
        header = True

    if '->' in key:
        # Get indirection data, the same function get_metas uses
        linkdata = add_matching_redirs(request, request.page, {}, {}, {},
                                       key, pagename, key)

        # Broken link, do not give anything editable as this will not
        # work in any case.
        if not linkdata:
            return fdata

        if key in linkdata:
            for pname in linkdata[key]:
                if not data:
                    pagename = pname
                    key = key.split('->')[-1]
                    break
                if data in linkdata[key][pname] or header:
                    pagename = pname
                    key = key.split('->')[-1]
                    break

    if data == fdata or header:
        return form_writer(
            u'<span data-page="%s" data-key="%s" data-index="%s">',
            pagename, key, str(id)) + fdata + '</span>'

    return form_writer(
        u'<span data-page="%s" data-key="%s" data-value="%s" data-index="%s">',
        pagename, key, data, str(id)) + fdata + '</span>'


def t_cell(request, cache, pageobj, vals, head=0,
           style=None, rev='', key='',
           pathstrip=0, linkoverride=''):
    formatter = request.formatter
    out = list()

    if style is None:
        style = dict()

    if "class" not in style:
        if head:
            style['class'] = 'meta_page'
        else:
            style['class'] = 'meta_cell'

    out.append(formatter.table_cell(1, attrs=style))
    cellstyle = style.get('gwikistyle', '').strip('"')

    if cellstyle == 'list':
        out.append(formatter.bullet_list(1))

    first_val = True

    for i, data in sorted(enumerate(vals), cmp=lambda x, y: cmp(x[1], y[1])):
        # cosmetic for having a "a, b, c" kind of lists
        if cellstyle not in ['list'] and not first_val:
            out.append(formatter.text(',') + formatter.linebreak())

        if head:
            if request.user.may.write(data):
                icon_cache = cache.get("icons")
                edit_icon = icon_cache.get("edit")
                formedit_icon = icon_cache.get("formedit")

                out.append(formatter.span(1, css_class="meta_editicon"))
                out.append(pageobj.link_to_raw(request, edit_icon,
                                               querystr={'action': 'edit'},
                                               rel='nofollow'))
                out.append(pageobj.link_to_raw(request, formedit_icon,
                                               querystr={'action':
                                                         'MetaFormEdit'},
                                               rel='nofollow'))
                out.append(formatter.span(0))
            kw = dict()
            if rev:
                kw['querystr'] = 'action=recall&rev=' + rev
            linktext = data
            if linkoverride:
                linktext = linkoverride
            elif pathstrip:
                dataparts = data.split('/')
                if pathstrip > len(dataparts):
                    pathstrip = len(dataparts) - 1
                if pathstrip:
                    linktext = '/'.join(reversed(
                        dataparts[:-pathstrip - 1:-1]))
            out.append(formatter.pagelink(1, data, **kw))
            out.append(formatter.text(linktext))
            out.append(formatter.pagelink(0))
        elif data.strip():
            if cellstyle == 'list':
                out.append(formatter.listitem(1))

            out.append(wrap_span(request, pageobj, key, data,
                                 i))

            if cellstyle == 'list':
                out.append(formatter.listitem(0))

        first_val = False

    if not vals:
        out.append(wrap_span(request, pageobj, key, '', 0))

    if cellstyle == 'list':
        out.append(formatter.bullet_list(1))

    out.append(formatter.table_cell(0))
    return out


def construct_table(request, cache, pagelist, metakeys, legend='',
                    checkAccess=True, styles=dict(),
                    options=dict()):
    request.page.formatter = request.formatter
    formatter = request.formatter
    _ = request.getText
    pagename = request.page.page_name

    row = 0

    formatopts = {'tableclass': 'metatable'}

    # Populate icon cache
    icon_cache = cache.setdefault("icons", dict())
    icon_cache["edit"] = request.theme.make_icon('edit')
    icon_cache["formedit"] = request.theme.make_icon('formedit')

    # Limit the maximum number of pages displayed
    pagepathstrip = options.get('pathstrip', 0)
    try:
        pagepathstrip = int(pagepathstrip)
    except ValueError:
        pagepathstrip = 0
    if pagepathstrip < 0:
        pagepathstrip = 0

    # Properties
    # Default and override properties
    propdefault = options.get('propdefault', '')
    propoverride = options.get('propoverride', '')
    if propoverride:
        propoverride = get_properties(request, propoverride)
    if propdefault:
        propdefault = get_properties(request, propdefault)
    # Properties dict per key
    properties = dict()
    emptyprop = dict().fromkeys(PROPERTIES, '')
    for key in metakeys:
        if propoverride:
            properties[key] = propoverride
        else:
            properties[key] = get_properties(request, key)
        if properties[key] == emptyprop:
            properties[key] = propdefault

    # To include only a [link] to page instead of pagename
    pagelinkonly = options.get('pagelinkonly', 0)
    # Transpose table, i.e. make table lanscape instead of portrait
    transpose = options.get('transpose', 0)

    # Limit the maximum number of pages displayed
    maxpages = len(pagelist)
    limit = options.get('limit', 0)
    try:
        limit = int(limit)
    except ValueError:
        limit = 0
    if limit > maxpages or limit < 0:
        limit = 0
    if limit:
        pagelist = pagelist[:limit]

    if 'width' in options:
        formatopts = {'tableclass': 'metatable wrap'}
        formatopts['tablewidth'] = options['width']

    # Start table
    out = list()
    out.append(formatter.linebreak() +
               formatter.table(1, attrs=formatopts))

    # If the first column is -, do not send page data
    send_pages = True
    if metakeys and metakeys[0] == '-':
        send_pages = False
        metakeys = metakeys[1:]

    if metakeys:
        # Give a class to headers to make it customisable
        out.append(formatter.table_row(1, {'rowclass': 'meta_header'}))
        if send_pages:
            # Upper left cell contains table size or has the desired legend
            if legend:
                out.extend(t_cell(request, cache, pagename, [legend]))
            elif limit:
                message = ["Showing (%s/%s) pages" %
                           (len(pagelist), maxpages)]

                out.extend(t_cell(request, cache, pagename, message))
            else:
                out.extend(t_cell(request, cache, pagename, [legend]))

    def key_cell(request, cache, metas, key, pageobj,
                 styles, properties):
        out = list()
        style = styles.get(key, dict())

        if key == 'gwikipagename':
            out.extend(t_cell(request, cache, pageobj, [pageobj.page_name],
                              head=1, style=style))
            return out

        colors = [x.strip() for x in properties
                  if x.startswith('color ')]
        colormatch = None
        # Get first color match
        for color in colors:
            colorval = properties.get(color)
            # See that color is valid (either in the colorlist
            # or a valid hex color)
            if colorval not in COLORS:
                if not re.match('#[0-9a-fA-F]{6}', colorval):
                    continue
            color = color.split()[-1]

            try:
                color_p = re.compile(color)
            except:
                continue
            for val in metas[key]:
                if color_p.match(val):
                    colormatch = colorval
            if colormatch:
                break
        if colormatch:
            style['bgcolor'] = colormatch

        out.extend(t_cell(request, cache, pageobj, metas[key],
                          style=style, key=key))

        if colormatch:
            del style['bgcolor']

        return out

    def page_rev_metas(request, page, metakeys, checkAccess):
        if '-gwikirevision-' in page:
            metas = get_metas(request, page, metakeys,
                              checkAccess=checkAccess)
            page, revision = page.split('-gwikirevision-')
        else:
            metas = get_metas(request, page, metakeys,
                              checkAccess=checkAccess)
            revision = ''

        return metas, page, revision

    def page_cell(request, cache, pageobj, revision, row, send_pages,
                  pagelinkonly, pagepathstrip):
        out = list()

        if row:
            if row % 2:
                out.append(formatter.table_row(1, {'rowclass':
                                                   'metatable-odd-row'}))

            else:
                out.append(formatter.table_row(1, {'rowclass':
                                                   'metatable-even-row'}))

        if send_pages:
            linktext = ''
            if pagelinkonly:
                linktext = _('[link]')
            out.extend(t_cell(request, cache, pageobj, [pageobj.page_name],
                              head=1, rev=revision, pathstrip=pagepathstrip,
                              linkoverride=linktext))

        return out

    tmp_page = request.page

    if transpose:
        for page in pagelist:
            metas, page, revision = page_rev_metas(request, page,
                                                   metakeys, checkAccess)

            pageobj = Page(request, page)
            request.page = pageobj
            request.formatter.page = pageobj

            out.extend(page_cell(request, cache, pageobj, revision, 0, send_pages,
                                 pagelinkonly, pagepathstrip))
    else:
        for key in metakeys:
            style = styles.get(key, dict())

            # Styles can modify key naming
            name = style.get('gwikiname', '').strip('"')

            if not name and legend and key == 'gwikipagename':
                name = [legend]

            # We don't want stuff like bullet lists in out header
            headerstyle = dict()
            for st in style:
                if not st.startswith('gwiki'):
                    headerstyle[st] = style[st]

            if name:
                out.extend(t_cell(request, cache, request.page, [name],
                                  style=headerstyle, key=key))
            else:
                out.extend(t_cell(request, cache, request.page, [key],
                                  style=headerstyle, key=key))

    if metakeys:
        out.append(formatter.table_row(0))

    if transpose:
        for key in metakeys:
            style = styles.get(key, dict())

            # Styles can modify key naming
            name = style.get('gwikiname', '').strip('"')

            if not name and legend and key == 'gwikipagename':
                name = [legend]

            # We don't want stuff like bullet lists in out header
            headerstyle = dict()
            for st in style:
                if not st.startswith('gwiki'):
                    headerstyle[st] = style[st]

            if name:
                out.extend(t_cell(request, cache, tmp_page, [name],
                                  style=headerstyle, key=key))
            else:
                out.extend(t_cell(request, cache, tmp_page, [key],
                                  style=headerstyle, key=key))

            row = row + 1

            for page in pagelist:
                metas, page, revision = page_rev_metas(request, page,
                                                       [key], checkAccess)

                pageobj = Page(request, page)
                request.page = pageobj
                request.formatter.page = pageobj

                out.extend(key_cell(request, cache, metas, key, pageobj,
                                    styles, properties[key]))

            out.append(formatter.table_row(0))
    else:
        for page in pagelist:
            metas, page, revision = page_rev_metas(request, page,
                                                   metakeys, checkAccess)

            row = row + 1

            pageobj = Page(request, page)
            request.page = pageobj
            request.formatter.page = pageobj

            out.extend(page_cell(request, cache, pageobj, revision, row,
                                 send_pages, pagelinkonly, pagepathstrip))

            for key in metakeys:
                out.extend(key_cell(request, cache, metas, key, pageobj,
                                    styles, properties[key]))

            out.append(formatter.table_row(0))

    request.page = tmp_page
    request.formatter.page = tmp_page

    out.append(formatter.table(0))
    return out


def do_macro(request, args, **kw):
    formatter = request.formatter
    _ = request.getText
    out = list()
    cache = dict()

    # Note, metatable_parseargs deals with permissions
    pagelist, metakeys, styles = metatable_parseargs(request, args,
                                                     get_all_keys=True)

    # No data -> bail out quickly, Scotty
    if not pagelist:
        out.append(formatter.linebreak() + u'<div class="metatable">' +
                   formatter.table(1))
        if kw.get('silent'):
            out.extend(t_cell(request, cache, request.page, ["%s" % _("No matches")]))
        else:
            out.extend(t_cell(request, cache, request.page,
                              ["%s '%s'" % (_("No matches for"), args)]))
        out.append(formatter.table(0) + u'</div>')
        return "".join(out)

    options = dict({'args': args}.items() + kw.items())
    divfmt = {'class': "metatable", 'data-options': quote(json.dumps(options))}
    out.append(formatter.div(1, **divfmt))
    # We're sure the user has the access to the page, so don't check
    out.extend(construct_table(request, cache, pagelist, metakeys,
                               checkAccess=False, styles=styles,
                               options=options))

    def action_link(action, linktext, args):
        req_url = request.script_root + "/" + \
            url_escape(request.page.page_name) + \
            '?action=' + action + '&amp;args=' + url_escape(args)
        return '<a href="%s" class="meta_footer_link">[%s]</a>\n' % \
            (req_url, _(linktext))

    # If the user has no write access to this page, omit editlink
    if kw.get('editlink', True):
        out.append(action_link('MetaEdit', 'edit', args))

    out.append(action_link('metaCSV', 'csv', args))
    out.append(action_link('metaPackage', 'zip', args))
    out.append(formatter.div(0))
    return "".join(out)


def execute(macro, args):
    request = macro.request

    if args is None:
        args = ''

    optargs = {}

    # Parse keyworded arguments (template etc)
    opts = re.findall("(?:^|,)\s*([^,|]+)\s*:=\s*([^,]+)\s*", args)
    args = re.sub("(?:^|,)\s*[^,|]+:=[^,]+\s*", "", args)
    for opt in opts:
        val = opt[1]
        if val == "True":
            val = True
        elif val == "False":
            val = False

        optargs[str(opt[0])] = val

    # loathful positional stripping (requires specific order of args), sorry
    if args.strip().endswith('gwikisilent'):
        optargs['silent'] = True
        args = ','.join(args.split(',')[:-1])

    if args.strip().endswith('noeditlink'):
        optargs['editlink'] = False
        args = ','.join(args.split(',')[:-1])

    return do_macro(request, args, **optargs)
