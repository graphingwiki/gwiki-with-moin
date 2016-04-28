# -*- coding: iso-8859-1 -*-
"""
    MoinMoin - RenamePage action

    This action allows you to rename a page.

    @copyright: 2002-2004 Michael Reinsch <mr@uue.org>,
                2006-2007 MoinMoin:ThomasWaldmann,
                2007 MoinMoin:ReimarBauer
                2009 Juhani Eronen <exec@iki.fi> (link renaming)
    @license: GNU GPL, see COPYING for details.
"""
import re
from MoinMoin import wikiutil
from MoinMoin.Page import Page
from MoinMoin.PageEditor import PageEditor
from MoinMoin.action import ActionBase
from MoinMoin.parser.text_moin_wiki import Parser

include_re = re.compile('(<<Include\(([^,\n]+)(.*?)\)>>)')

class RenamePage(ActionBase):
    """ Rename page action

    Note: the action name is the class name
    """
    def __init__(self, pagename, request):
        ActionBase.__init__(self, pagename, request)
        self.use_ticket = True
        _ = self._
        self.form_trigger = 'rename'
        self.form_trigger_label = _('Rename Page')
        filterfn = re.compile(ur"^%s/.*$" % re.escape(pagename), re.U).match
        subpagenames = request.rootpage.getPageList(user='', exists=1, filter=filterfn)
        self.subpages = [pagename for pagename in subpagenames if self.request.user.may.delete(pagename)]
        try:
            self.show_redirect = request.cfg.show_rename_redirect
        except AttributeError:
            self.show_redirect = False
        try:
            self.rename_redirect = int(self.request.form.get('rename_redirect', '0'))
        except ValueError:
            self.rename_redirect = 0
        try:
            self.rename_inlinks = int(self.request.form.get('rename_inlinks', '0'))
        except ValueError:
            self.rename_inlinks = 0

    def is_allowed(self):
        may = self.request.user.may
        return may.write(self.pagename) and may.delete(self.pagename)

    def check_condition(self):
        _ = self._
        if not self.page.exists():
            return _('This page is already deleted or was never created!')
        else:
            return None

    def _inlink_rename(self, page, newpagename, oldpagename, comment):
        rel_newpagename = wikiutil.RelPageName(page, newpagename)

        # The following regexp match functions search for
        # occurrences of the target page name, determine
        # if they're absolute, relative or subpage
        # matches, and replace them accordingly
        def word_subfun(mo):
            match = mo.groups()

            if wikiutil.AbsPageName(page, match[1]) == oldpagename:
                # If the link was relative:
                if not oldpagename in match[1]:
                    # If the new page will be a subpage of the
                    # source, retain relative link. Else, make
                    # an absolute link.
                    if (rel_newpagename.startswith('/') or
                        rel_newpagename.startswith('../')):
                        return match[1].replace(
                            wikiutil.RelPageName(page, oldpagename),
                            rel_newpagename)
                    else:
                        return match[1].replace(
                            wikiutil.RelPageName(page, oldpagename),
                            newpagename)

                # Else, change absolute link
                return match[1].replace(oldpagename, newpagename)
            # No match in this link -> move on
            else:
                return match[1]

        def link_subfun(mo):
            match = mo.groups()

            if wikiutil.AbsPageName(page, match[1]) == oldpagename:
                # If the link was relative:
                if not oldpagename in match[0]:
                    # If the new page will be a subpage of the
                    # source, retain relative link. Else, make
                    # an absolute link.
                    if (rel_newpagename.startswith('/') or
                        rel_newpagename.startswith('../')):
                        return match[0].replace(
                            wikiutil.RelPageName(page, oldpagename),
                            rel_newpagename)
                    else:
                        return match[0].replace(
                            wikiutil.RelPageName(page, oldpagename),
                            newpagename)

                # Else, change absolute link
                return match[0].replace(oldpagename, newpagename)
            # No match in this link -> move on
            else:
                return match[0]

        def include_subfun(mo):
            match = mo.groups()

            if wikiutil.AbsPageName(page, match[1]) == oldpagename:
                # If the link was relative:
                if not oldpagename in match[0]:
                    # If the new page will be a subpage of the
                    # source, retain relative link. Else, make
                    # an absolute link.
                    if (rel_newpagename.startswith('/') or
                        rel_newpagename.startswith('../')):
                        return match[0].replace(
                            wikiutil.RelPageName(page, oldpagename),
                            rel_newpagename)
                    else:
                        return match[0].replace(
                            wikiutil.RelPageName(page, oldpagename),
                            newpagename)

                # Else, change absolute link
                return match[0].replace(oldpagename, newpagename)
            # No match in this link -> move on
            else:
                return match[0]

        self.page = PageEditor(self.request, page)
        savetext = self.page.get_raw_body()

        # Must replace both WikiWords and links, as
        # [[WikiWord]] is a link.
        word_re = re.compile(Parser.word_rule, re.VERBOSE)
        savetext = word_re.sub(word_subfun, savetext)
        link_re = re.compile(Parser.link_rule, re.VERBOSE)
        savetext = link_re.sub(link_subfun, savetext)

        # Also handle renaming (non-regexped) includes of the page
        savetext = include_re.sub(include_subfun, savetext)

        _ = self.request.getText

        success = True

        try:
            msg = self.page.saveText(savetext, 0, comment=comment,
                                     notify=False)
        except self.page.Unchanged:
            msg = _('Error changing links on page %s!') % (self.page.page_name)
            success = False

        return success, msg

    def rename_inlinks(self, newpagename, comment, msgs):
        comment = "%s (%s)" % (comment, _("changed links:") +
                               " %s -> %s" % (self.pagename, newpagename))
        # List pages that link to the renamed page
        pages = set()
        inlinks = self.request.graphdata.get_in(self.pagename)
        for type in inlinks:
            pages.update(inlinks[type])

        # Update listed pages
        for page in pages:
            # User rights _ARE_ checked here!
            if not self.request.user.may.write(page):
                continue

            # If inlink rename of a single page does not work,
            # continue but make sure to emit a warning
            success_i, msg = self._inlink_rename(page, newpagename,
                                                 oldpagename, comment)
            if not success_i:
                success = False

            if msg:
                msgs.append(msg)

        if not success:
            msgs.append(_(u'Other pages with inlinks renamed successfully.'))

        return success, msgs

    def do_action(self):
        """ Rename this page to "pagename" """
        _ = self._
        form = self.form
        newpagename = form.get('newpagename', u'')
        newpagename = wikiutil.normalize_pagename(newpagename, self.cfg)
        comment = form.get('comment', u'')
        comment = wikiutil.clean_input(comment)
        try:
            rename_subpages = int(self.request.form.get('rename_subpages', '0'))
        except ValueError:
            rename_subpages = 0

        self.page = PageEditor(self.request, self.pagename)
        success, msgs = self.page.renamePage(newpagename, comment)

        if not success:
            return success, msgs

        msgs = [msgs]

        if rename_inlinks:
            success, msgs = self.rename_inlinks(newpagename, comment, msgs)

        if self.show_redirect and self.rename_redirect:
            self.page = PageEditor(self.request, self.pagename)
            self.page.saveText('#redirect %s' % newpagename, 0)

        if rename_subpages and self.subpages:
            for name in self.subpages:
                self.page = PageEditor(self.request, name)
                new_subpagename = name.replace(self.pagename, newpagename, 1)
                success_i, msg = self.page.renamePage(new_subpagename, comment)
                msgs.append(msg)

                if self.show_redirect and self.rename_redirect and success_i:
                    self.page = PageEditor(self.request, name)
                    self.page.saveText('#redirect %s' % new_subpagename, 0)
            msgs = ' '.join([msg for msg in msgs if msg])

        self.newpagename = newpagename # keep there for finish
        return success, msgs

    def do_action_finish(self, success):
        if success:
            url = Page(self.request, self.newpagename).url(self.request)
            self.request.http_redirect(url, code=301)
        else:
            self.render_msg(self.make_form(), "dialog")

    def get_form_html(self, buttons_html):
        _ = self._

        if self.subpages:
            redirect_label = _('Create redirect for renamed page(s)?')

            subpages = ' '.join([wikiutil.escape(page) for page in self.subpages])
            subpages_html = """
                <tr>
                <dd>
                    %(subpage_label)s<input type="checkbox" name="rename_subpages" value="1" %(subpages_checked)s>
                </dd>
                <dd>
                    <class="label"><subpage> %(subpage)s</subpage>
                </dd>
                </tr>
                """ % {
                    'subpage': subpages,
                    'subpages_checked': ('', 'checked')[self.request.args.get('subpages_checked', '0') == '1'],
                    'subpage_label': _('Rename all /subpages too?'),
                 }
        else:
            redirect_label = _('Create redirect for renamed page?')
            subpages_html = ""

        if self.show_redirect:
            redirect_html = '<tr><dd>%(redirect_label)s<input type="checkbox" name="rename_redirect" value="1" %(redirect)s></dd></tr>' % {
                'redirect': self.rename_redirect,
                'redirect_label': redirect_label,
            }
        else:
            redirect_html = ''

        if self.show_redirect or self.subpages:
            options_html = """
                <table>
                    %(subpages_html)s
                    %(redirect_html)s
                </table>
                """ % {
                    "subpages_html": subpages_html,
                    "redirect_html": redirect_html,
                }
        else:
            options_html = ""

        d = {
            'querytext': _('Really rename this page?'),
            'pagename': wikiutil.escape(self.pagename, True),
            'newname_label': _("New name"),
            'comment_label': _("Optional reason for the renaming"),
            'inlinks_label': _('Rename links to page too?'),
            'inlinks_checked': ('', 'checked')[self.request.args.get('inlinks_checked', '0') == '1'],
            'buttons_html': buttons_html,
            'options_html': options_html,
            }

        return '''
<strong>%(querytext)s</strong>
<br>
<br>
%(options_html)s
<table>
    <tr>
        <td class="label"><label>%(newname_label)s</label></td>
        <td class="content">
            <input type="text" name="newpagename" value="%(pagename)s" size="80">
        </td>
    </tr>
    <tr>
        <td class="label"><label>%(comment_label)s</label></td>
        <td class="content">
            <input type="text" name="comment" size="80" maxlength="200">
        </td>
    </tr>
    <tr>
    <td>
    <dd>
        %(inlinks_label)s<input type="checkbox" name="rename_inlinks" value="1" %(inlinks_checked)s>
    </dd>
    </td>
    </tr>
    <tr>
        <td></td>
        <td class="buttons">
            %(buttons_html)s
        </td>
    </tr>
</table>
''' % d

def execute(pagename, request):
    """ Glue code for actions """
    RenamePage(pagename, request).render()

