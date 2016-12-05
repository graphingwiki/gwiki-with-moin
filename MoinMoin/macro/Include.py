# -*- coding: utf-8 -*-
"""
    Include macro for MoinMoin/GraphingWiki

    Partial rewrite of orginal Include macro.

    New features:
     * Including nonexisting pages with an editlink
     * Specifying a template for editing, eg.
     <<Include(Case183/nonexisting,,,editlink,template="HelpTemplate")>>
     * Specifying a revision for included pages, eg.
     <<Include(FrontPage,,,editlink,rev=1)>>

    @copyright: 2000-2004 Juergen Hermann <jh@web.de>,
                2000-2001 Richard Jones <richard@bizarsoftware.com.au>,
                2009-2011 Juhani Eronen <exec@iki.fi>,
                2015-2016 Mika Seppänen <mika.seppanen@iki.fi>
    @license: GNU GPL, see COPYING for details.
"""

Dependencies = ["time"]  # works around MoinMoinBugs/TableOfContentsLacksLinks

generates_headings = True

import re
import StringIO

from MoinMoin import wikiutil
from MoinMoin.Page import Page

from graphingwiki import actionname, id_escape, SEPARATOR
from graphingwiki.util import render_error, render_warning
from graphingwiki.util import form_writer as wr

_arg_heading = r'(?P<heading>,)\s*(|(?P<hquote>[\'"])(?P<htext>.+?)(?P=hquote))'
_arg_level = r',\s*(?P<level>\d*)'
_arg_from = r'(,\s*from=(?P<fquote>[\'"])(?P<from>.+?)(?P=fquote))?'
_arg_to = r'(,\s*to=(?P<tquote>[\'"])(?P<to>.+?)(?P=tquote))?'
_arg_sort = r'(,\s*sort=(?P<sort>(ascending|descending)))?'
_arg_items = r'(,\s*items=(?P<items>\d+))?'
_arg_skipitems = r'(,\s*skipitems=(?P<skipitems>\d+))?'
_arg_titlesonly = r'(,\s*(?P<titlesonly>titlesonly))?'
_arg_editlink = r'(,\s*(?P<editlink>editlink))?'
_arg_rev = r'(,\s*rev=(?P<rev>\d+))?'
_arg_template = r'(,\s*template=(?P<tequot>[\'"])(?P<template>.+?)(?P=tequot))?'
_args_re_pattern = r'^(?P<name>[^,]+)(%s(%s)?%s%s%s%s%s%s%s%s%s)?$' % (
    _arg_heading, _arg_level, _arg_from, _arg_to, _arg_sort, _arg_items,
    _arg_skipitems, _arg_titlesonly, _arg_editlink, _arg_rev, _arg_template)

_title_re = r"^(?P<heading>\s*(?P<hmarker>=+)\s.*\s(?P=hmarker))$"


def extract_titles(body, title_re):
    titles = []
    for title, _ in title_re.findall(body):
        h = title.strip()
        level = 1
        while h[level:level + 1] == '=':
            level += 1
        title_text = h[level:-level].strip()
        titles.append((title_text, level))
    return titles


def execute(macro, text, args_re=re.compile(_args_re_pattern), title_re=re.compile(_title_re, re.M)):
    request = macro.request
    _ = request.getText

    # return immediately if getting links for the current page
    if request.mode_getpagelinks:
        return ''

    # parse and check arguments
    args = text and args_re.match(text)
    if not args:
        return render_error(_('Invalid include arguments "%s"!') % (text,))

    # prepare including page
    result = []
    print_mode = request.action in ("print", "format")
    this_page = macro.formatter.page
    if not hasattr(this_page, '_macroInclude_pagelist'):
        this_page._macroInclude_pagelist = {}

    # get list of pages to include
    inc_name = wikiutil.AbsPageName(this_page.page_name, args.group('name'))
    pagelist = [inc_name]
    if inc_name.startswith("^"):
        try:
            inc_match = re.compile(inc_name)
        except re.error:
            pass  # treat as plain page name
        else:
            # Get user filtered readable page list
            pagelist = request.rootpage.getPageList(filter=inc_match.match)

    specific_page = not inc_name.startswith("^")

    rev = args.group("rev")
    if specific_page and rev is not None:
        try:
            rev = int(rev)
        except (ValueError, UnicodeDecodeError):
            rev = None
    else:
        rev = None

    # sort and limit page list
    pagelist.sort()
    sort_dir = args.group('sort')
    if sort_dir == 'descending':
        pagelist.reverse()
    max_items = args.group('items')
    if max_items:
        pagelist = pagelist[:int(max_items)]

    skipitems = 0
    if args.group("skipitems"):
        skipitems = int(args.group("skipitems"))
    titlesonly = args.group('titlesonly')
    editlink = args.group('editlink')

    # iterate over pages
    for inc_name in pagelist:
        if not request.user.may.read(inc_name):
            continue

        if inc_name in this_page._macroInclude_pagelist:
            result.append(render_error(_('Recursive include of "%s" forbidden!') % (inc_name,)))
            continue

        if skipitems > 0:
            skipitems -= 1
            continue

        fmt = macro.formatter.__class__(request, is_included=True)
        fmt._base_depth = macro.formatter._base_depth

        if specific_page and rev is not None:
            inc_page = Page(request, inc_name, formatter=fmt, rev=rev)
        else:
            inc_page = Page(request, inc_name, formatter=fmt)

        inc_page._macroInclude_pagelist = this_page._macroInclude_pagelist

        page_exists = inc_page.exists()

        # check for "from" and "to" arguments (allowing partial includes)
        if page_exists:
            body = inc_page.get_raw_body() + '\n'
        else:
            body = ""

        from_pos = 0
        to_pos = -1
        from_re = args.group('from')
        if page_exists and from_re:
            try:
                from_match = re.compile(from_re, re.M).search(body)
            except re.error:
                from_match = re.compile(re.escape(from_re), re.M).search(body)
            if from_match:
                from_pos = from_match.end()
            else:
                result.append(render_warning(_('Include: Nothing found for "%s"!') % from_re))

        to_re = args.group('to')
        if page_exists and to_re:
            try:
                to_match = re.compile(to_re, re.M).search(body, from_pos)
            except re.error:
                to_match = re.compile(re.escape(to_re), re.M).search(body, from_pos)
            if to_match:
                to_pos = to_match.start()
            else:
                result.append(render_warning(_('Include: Nothing found for "%s"!') % to_re))

        if titlesonly:
            levelstack = []
            for title, level in extract_titles(body[from_pos:to_pos], title_re):
                if levelstack:
                    if level > levelstack[-1]:
                        result.append(macro.formatter.bullet_list(1))
                        levelstack.append(level)
                    else:
                        while levelstack and level < levelstack[-1]:
                            result.append(macro.formatter.bullet_list(0))
                            levelstack.pop()
                        if not levelstack or level != levelstack[-1]:
                            result.append(macro.formatter.bullet_list(1))
                            levelstack.append(level)
                else:
                    result.append(macro.formatter.bullet_list(1))
                    levelstack.append(level)
                result.append(macro.formatter.listitem(1))
                result.append(inc_page.link_to(request, title))
                result.append(macro.formatter.listitem(0))
            while levelstack:
                result.append(macro.formatter.bullet_list(0))
                levelstack.pop()
            continue

        if from_pos or to_pos != -1:
            inc_page.set_raw_body(body[from_pos:to_pos], modified=True)

        if not hasattr(request, "_Include_backto"):
            request._Include_backto = this_page.page_name

        # do headings
        level = None
        if args.group('heading') and args.group('hquote'):
            heading = args.group('htext') or inc_page.split_title()
            level = 1
            if args.group('level'):
                level = int(args.group('level'))
            if print_mode:
                result.append(macro.formatter.heading(1, level) +
                              macro.formatter.text(heading) +
                              macro.formatter.heading(0, level))
            else:
                url = inc_page.url(request)
                result.extend([
                    macro.formatter.heading(1, level, id=heading),
                    macro.formatter.url(1, url, css="include-heading-link"),
                    macro.formatter.text(heading),
                    macro.formatter.url(0),
                    macro.formatter.heading(0, level),
                ])

        # set or increment include marker
        this_page._macroInclude_pagelist[inc_name] = \
            this_page._macroInclude_pagelist.get(inc_name, 0) + 1

        # output the included page
        strfile = StringIO.StringIO()
        request.redirect(strfile)
        try:
            request.write(
                request.formatter.div(True,
                                      css_class='gwikiinclude',
                                      id=id_escape(inc_name) + SEPARATOR))
            inc_page.send_page(content_only=True,
                               omit_footnotes=True,
                               count_hit=False)
            request.write(request.formatter.div(False))
            result.append(strfile.getvalue())
        finally:
            request.redirect()

        # decrement or remove include marker
        if this_page._macroInclude_pagelist[inc_name] > 1:
            this_page._macroInclude_pagelist[inc_name] = \
                this_page._macroInclude_pagelist[inc_name] - 1
        else:
            del this_page._macroInclude_pagelist[inc_name]

        template = args.group("template")

        # if no heading and not in print mode, then output a helper link
        if editlink and not (level or print_mode):
            result.append(macro.formatter.div(1, css_class="include-link"))

            if specific_page and not page_exists:
                result.append("[%s]" % (inc_name,))
                if template:
                    result.append(inc_page.link_to(request, '[%s]' % (_('create'), ), css_class="include-edit-link", querystr={'action': 'edit', 'backto': request._Include_backto, 'template': template}))
                else:
                    out = wr('<form method="GET" action="%s">\n',
                             actionname(request, request._Include_backto))
                    out += wr('<select name="template">\n')
                    out += wr('<option value="">%s</option>\n',
                              _("No template"))

                    # Get list of template pages readable by current user
                    filterfn = request.cfg.cache.page_template_regexact.search
                    templates = request.rootpage.getPageList(filter=filterfn)
                    for i in templates:
                        out += wr('<option value="%s">%s</option>\n', i, i)

                    out += '</select>\n'
                    out += '<input type="hidden" name="action" value="newpage">\n'
                    out += wr('<input type="hidden" name="pagename" value="%s">\n', inc_name)
                    out += wr('<input type="submit" value="%s">\n', _('create'))
                    out += wr('</form>\n')
                    result.append(out)
            elif specific_page and rev is not None:
                result.extend([
                    inc_page.link_to(request, '[%s revision %d]' % (inc_name, rev), querystr={"action": "recall", "rev": str(rev)}, css_class="include-page-link"),
                    inc_page.link_to(request, '[%s]' % (_('edit current version'), ), css_class="include-edit-link", querystr={'action': 'edit', 'backto': request._Include_backto}),
                ])
            else:
                result.extend([
                    inc_page.link_to(request, '[%s]' % (inc_name, ), css_class="include-page-link"),
                    inc_page.link_to(request, '[%s]' % (_('edit'), ), css_class="include-edit-link", querystr={'action': 'edit', 'backto': request._Include_backto}),
                ])

            result.append(macro.formatter.div(0))

        # XXX page.link_to is wrong now, it escapes the edit_icon html as it escapes normal text

    # return include text
    return ''.join(result)
