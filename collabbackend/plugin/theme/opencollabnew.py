# -*- coding: utf-8 -*-
"""
    MoinMoin - Bootstrap theme.

    Based on the Ficora theme (c) by Pasi Kemi 
    (Media Agency Bears: http://www.mediakarhut.fi)

    Modifications by Juhani Eronen <exec@iki.fi> and Lauri Pokka

    @license: GNU GPL <http://www.gnu.org/licenses/gpl.html>
"""
import re

from MoinMoin import wikiutil
from MoinMoin.Page import Page
from MoinMoin.theme.modernized import Theme as ThemeParent
from MoinMoin.theme import get_available_actions

from graphingwiki.plugin.macro.LinkedIn import nodes

# FIXME: Caching of relevant portions

BREADCRUMB_ACTIONS = [
    'print',
    'raw',
    'info',
    'AttachFile',
    'Invite',
]

EDIT_ACTIONS = [
    'revert',
    'CopyPage',
    'RenamePage',
    'DeletePage',
    'MetaFormEdit',
    'MetaEdit',
]

ACTION_NAMES = {
    'info': 'Info',
    'edit': 'Edit',
    'AttachFile': 'Attachments',
    'raw': 'Raw Text',
    'print': 'Print View',
    'refresh': 'Delete Cache',
    'SpellCheck': 'Check Spelling',
    'RenamePage': 'Rename Page',
    'CopyPage': 'Copy Page',
    'DeletePage': 'Delete Page',
    'LikePages': 'Like Pages',
    'LocalSiteMap': 'Local Site Map',
    'MyPages': 'My Pages',
    'SubscribeUser': 'Subscribe User',
    'Despam': 'Remove Spam',
    'revert': 'Revert to this revision',
    'PackagePages': 'Package Pages',
    'RenderAsDocbook': 'Render as Docbook',
    'SyncPages': 'Sync Pages',
    'Invite': 'Invite',
}

BOOTSTRAP_THEME_CSS = [
    ("all", "bootstrap.min")
]

QUICKLINKS_RE = re.compile('<li class="userlink">.+?</li>', re.M)

NAME = "opencollabnew"
THEME_PATH = "../../" + NAME


class Theme(ThemeParent):
    name = NAME
    rev = ''
    available = ''

    css_files = []

    GLYPHICONS = {
        'FrontPage': 'glyphicon glyphicon-home',
        'CollabList': 'glyphicon glyphicon-list',
        'edit': 'glyphicon glyphicon-edit',
        'RecentChanges': 'glyphicon glyphicon-time',
    }

    def __init__(self, request):
        ThemeParent.__init__(self, request)
        sheetsnames = ['stylesheets', 'stylesheets_print', 'stylesheets_projection']

        # include css and icon files from this theme when in inherited theme
        if self.name is not NAME:
            for sheetsname in sheetsnames:
                theme_sheets = getattr(self, sheetsname)
                parent_sheets = []
                for sheet in theme_sheets:
                    link = (sheet[0], THEME_PATH + "/css/" + sheet[1])
                    parent_sheets.append(link)

                # remove css files that are not defined in css_files of the inherited theme
                theme_sheets = [sheet for sheet in theme_sheets if sheet[1] in self.css_files]
                setattr(self, sheetsname, tuple(parent_sheets + theme_sheets))

            for key, val in self.icons.items():
                val = list(val)
                val[1] = THEME_PATH + "/img/" + val[1]
                self.icons[key] = tuple(val)

        # bootstrap css file should be before themes
        for sheet in reversed(BOOTSTRAP_THEME_CSS):
            link = (sheet[0], "../../bootstrap/css/" + sheet[1])
            self.stylesheets = (link,) + self.stylesheets

        self.available = get_available_actions(request.cfg,
                                               request.page,
                                               request.user)

    def logo(self):
        mylogo = ThemeParent.logo(self)
        if not mylogo:
            mylogo = u'''<span>%s</span>''' % \
                     wikiutil.escape(self.cfg.sitename, True)

        return mylogo

    def _actiontitle(self, action):
        _ = self.request.getText
        name = ACTION_NAMES.get(action, action)
        return _(name)

    def editmenu(self, d):
        request = self.request
        page = self.request.page
        _ = request.getText
        guiworks = self.guiworks(page)
        editor = request.user.editor_default
        editdisabled = False

        editurl = u"?action=edit"

        if not 'edit' in request.cfg.actions_excluded:
            if not (page.isWritable() and request.user.may.write(page.page_name)):
                editdisabled = True
            elif guiworks and editor == 'gui':
                editurl += u"&editor=gui"
        else:
            editdisabled = True

        links = []

        if editdisabled:
            return u""

        for action in EDIT_ACTIONS:
            disabled = False

            if action == 'revert':
                if not request.user.may.revert(page.page_name) or not request.rev:
                    disabled = True

            if not disabled:
                link = u'<li><a href="?action=%s%s">%s</a></li>' % (action, self.rev, self._actiontitle(action))
                links.append(link)

        return u"""
    <ul class="nav navbar-nav editmenu">
        <li>
            <a href="%s" title="%s"><i class="glyphicon glyphicon-edit"></i></a>
        </li>
        <li>
            <a class="dropdown-toggle" data-toggle="dropdown"><i class="caret"></i></a>
            <ul class="dropdown-menu">
                %s
            </ul>
        </li>
    </ul>""" % (editurl, _('Edit'), (u"\n" + u" "*10).join(links))

    def actionsmenu(self, d):
        request = self.request
        page = self.request.page
        _ = request.getText

        ignored = [
            'Despam',
            'SpellCheck',
            'LikePages',
            'LocalSiteMap',
            'RenderAsDocbook',
            'MyPages',
            'SubscribeUser',
            'N3Dump',
            'RdfInfer',
            'Invite',
            'PackagePages',
            'Load',
            'Save',
        ]

        ignored += EDIT_ACTIONS + BREADCRUMB_ACTIONS

        links = []

        links.append(u'<li>%s</li>\n' % (self.quicklinkLink(page)))

        if self.subscribeLink(page):
            links.append(u'<li>%s</li>\n' % (self.subscribeLink(page)))

        more = [item for item in self.available if item not in ignored]
        more.sort()

        for action in more:
            link = u'<li><a href="?action=%s%s">%s</a></li>' % (action, self.rev, self._actiontitle(action))
            links.append(link)

        return u"""
        <li>
            <a title="%s" class="dropdown-toggle" data-toggle="dropdown">
                <i class="glyphicon glyphicon-wrench"></i>
            </a>
            <ul class="dropdown-menu">
                %s
            </ul>
        </li>""" % (_("More Actions:"),  (u"\n" + u" "*10).join(links))

    def navibar(self, d, *items):
        """ Assemble the navibar

        @param d: parameter dictionary
        @rtype: unicode
        @return: navibar html
        """
        request = self.request
        found = {} # pages we found. prevent duplicates
        links = [] # navibar items
        item = u'<li class="%s">%s</li>'
        item_icon = u' title="%s"><i class="%s"></i><'
        current = d['page_name']

        default_items = [
            getattr(request.cfg, 'page_front_page', u"FrontPage"),
            u'RecentChanges',
        ]

        nav_items = getattr(request.cfg, 'navi_bar_new', default_items)

        for text in nav_items:
            pagename, link = self.splitNavilink(text)
            if pagename in self.GLYPHICONS:
                icon = item_icon % (pagename, self.GLYPHICONS[pagename])
                link = link.replace(">%s<" % pagename, icon)
            if pagename == current:
                cls = 'wikilink current'
            else:
                cls = 'wikilink'
            links.append(item % (cls, link))
            found[pagename] = 1

        # Add user links to wiki links, eliminating duplicates.
        #userlinks = request.user.getQuickLinks()
        #for text in userlinks:
        #    # Split text without localization, user knows what he wants
        #    pagename, link = self.splitNavilink(text, localize=0)
        #    if not pagename in found:
        #        if pagename == current:
        #            cls = 'userlink current'
        #        else:
        #            cls = 'userlink'
        #        items.append(item % (cls, link))
        #        found[pagename] = 1

        return  u"""
    <div class="navbar navbar-inverse navbar-fixed-top">
        <div class="navbar-header">
            <button type="button" class="navbar-toggle" data-toggle="collapse"
                    data-target="#main-nav">
              <span class="icon-bar"></span>
              <span class="icon-bar"></span>
              <span class="icon-bar"></span>
            </button>
            <div id="logo" class="navbar-brand">
                <a href="CollabList">
                    %s
                </a>
            </div>
        </div>
        <div class="collapse navbar-collapse" id="main-nav">
            <ul class="nav navbar-nav">
                %s
            </ul>
            %s
        </div>
    </div>""" % (self.logo(),  u'\n'.join(links), u'\n'.join(items))

    def username(self, d):
        request = self.request
        _ = request.getText

        userlinks = []
        # Add username/homepage link for registered users. We don't care
        # if it exists, the user can create it.
        if request.user.valid and request.user.name:
            interwiki = wikiutil.getInterwikiHomePage(request)
            linkpage = '#'
            if interwiki[0] == 'Self':
                wikitail = wikiutil.url_unquote(interwiki[1])
                linkpage = request.script_root + '/' + wikitail

            name = request.user.name
            urls = []

            plugins = wikiutil.getPlugins('userprefs', request.cfg)
            for sub in plugins:
                if sub in request.cfg.userprefs_disabled:
                    continue
                cls = wikiutil.importPlugin(request.cfg, 'userprefs',
                                            sub, 'Settings')
                obj = cls(request)
                if not obj.allowed():
                    continue
                url = request.page.url(request, {'action': 'userprefs',
                                                 'sub': sub})
                urls.append('<a href="%s">%s</a>' % (url, obj.title))

            out = ""

            if urls:
                out = u"""
                  <div class="input-group-btn">
        <button type="button" class="btn btn-default dropdown-toggle" data-toggle="dropdown">
          <i class="glyphicon glyphicon-user"></i></span>
        </button>
        <ul class="dropdown-menu navbar-right">
            <li class="nav-header"><a href="%s">%s</a></li>
                """ % (linkpage, name)

                for url in urls:
                    out += "                  <li>%s</li>\n" % url

                out += u"""
                </ul>
            </div>"""

            return out

    def search_user_form(self, d):
        _ = self.request.getText
        url = self.request.href(d['page'].page_name)

        return u"""
  <form method="get" action="%s">
    <div class="input-group navbar-form form-group navbar-right">
                <input type="hidden" name="action" value="fullsearch">
                <input type="hidden" name="context" value="180">
          <input class="form-control search" placeholder="Search" name="value">
            <span class="input-group-btn">
                <button class="btn btn-primary" name="titlesearch" type="submit">
                    <i class="glyphicon glyphicon-search"></i>
                </button>
            </span>
        %s
    </div>
</form>

        """ % (url, self.username(d))

    def header(self, d, **kw):
        """ Assemble wiki header

        @param d: parameter dictionary
        @rtype: unicode
        @return: page header html
        """
        if self.request.rev:
            if self.request.page.current_rev() != self.request.rev:
                self.rev = '&rev=%d' % (self.request.rev)
        else:
            self.rev = ''

        html = [
            # Pre header custom html
            self.emit_custom_html(self.cfg.page_header1),

            # Header
            u'<div id="header">',

            # Top-padding element that has height that matches
            # the height of the fixed position top navbar. Adding
            # padding to body would be normal approach, but some
            # pages that don't have the navbar, such as editors
            # would then show the extra padding on top.
            u'<div id="top-padding"></div>',


            self.navibar(
                d,
                self.editmenu(d),
                self.search_user_form(d)
            ),
            self.breadcrumbs(d),
            self.msg(d),
            u'</div> <!-- /header -->',

            # Post header custom html (not recommended)
            self.emit_custom_html(self.cfg.page_header2),

            # Start of page
            self.startPage(),
        ]
        return u'\n'.join(html)

    def breadcrumbs(self, d):
        request = self.request
        _ = request.getText
        user = request.user
        items = []

        if not user.valid or user.show_page_trail:
            trail = user.getTrail()
            if trail:
                for pagename in trail:
                    try:
                        interwiki, page = wikiutil.split_interwiki(pagename)
                        if interwiki != request.cfg.interwikiname \
                            and interwiki != 'Self':
                            link = (
                                self.request.formatter.interwikilink(
                                    True, interwiki, page) +
                                self.shortenPagename(page) +
                                self.request.formatter.interwikilink(
                                    False, interwiki, page))
                            items.append(link)
                            continue
                        else:
                            pagename = page
                    except ValueError:
                        pass
                    page = Page(request, pagename)
                    title = page.split_title()
                    title = self.shortenPagename(title)
                    link = page.link_to(request, title)
                    items.append(link)

        val = """  <div class="navbar breadcrumb">
    <ul class="breadcrumb navbar-left">"""

        for item in items:
            val += '\n      <li>%s</li>' % item

        val += '\n    </ul>\n    <ul class="breadcrumb navbar-right">'
        actions = getattr(request.cfg, 'bootstrap_actions',
                          BREADCRUMB_ACTIONS)
        for i, act in enumerate(actions):
            if act[0].isupper() and not act in self.available:
                continue
            val += '\n      <li><a href="?action=%s%s">%s</a></li>' % (act, self.rev,  self._actiontitle(act))

        val += u"""
      <li class="toggleCommentsButton" style="display:none;">
          <a href="#" class="nbcomment" onClick="toggleComments(); return false;">%s</a>
      </li>
        %s
    </ul>
  </div>""" % (_('Comments'), self.actionsmenu(d))


        return val

    def linkedin(self):
        if not getattr(self.request.cfg, 'theme_linkedin', True):
            return ''
        _ = self.request.getText

        val = ''
        li = nodes(self.request, self.request.page.page_name, False)
        if not li:
            return val

        val = '<div id="message">\n<ul class="inline">\n<li>%s</li>\n' % \
              _("Linked in pages")
        for l in li:
            val += '<li>%s</li>' % l
        val += '</div>\n'
        return val

    def footer_string(self):
        if hasattr(self.cfg, 'footer_string'):
            footer_string = self.cfg.footer_string
        else:
            footer_string = '<p class="footertext"></p>'

        return footer_string

    def footer(self, d, **keywords):
        """ Assemble wiki footer

        @param d: parameter dictionary
        @keyword ...:...
        @rtype: unicode
        @return: page footer html
        """

        page = d['page']
        html = [
            # End of page
            self.endPage(),

            u'<script src="' + self.cfg.url_prefix_static + \
            u'/bootstrap/js/bootstrap.js"></script>',

            # Pre footer custom html (not recommended!)
            self.emit_custom_html(self.cfg.page_footer1),

            self.linkedin(),

            # Footer
            self.breadcrumbs(d),
            u'<div id="footer">',
            self.pageinfo(page),
            self.footer_string(),
            u'</div>',

            # Post footer custom html
            self.emit_custom_html(self.cfg.page_footer2),
        ]
        return u'\n'.join(html)


def execute(request):
    """
    Generate and return a theme object

    @param request: the request object
    @rtype: MoinTheme
    @return: Theme object
    """
    return Theme(request)

