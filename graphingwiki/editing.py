# -*- coding: utf-8 -*-
"""
    Graphingwiki editing functions
     - Saving page contents or relevant metadata

    @copyright: 2007 by Juhani Eronen, Erno Kuusela and Joachim Viide
    @license: MIT <http://www.opensource.org/licenses/mit-license.php>
"""
import os
import re
import string
import socket
import copy
import operator

try:
    from hashlib import md5
except ImportError:
    from md5 import md5

from MoinMoin.action.AttachFile import getAttachDir, getFilename, _addLogEntry
from MoinMoin.PageEditor import PageEditor
from MoinMoin.Page import Page
from MoinMoin import wikiutil
from MoinMoin import config
from MoinMoin import caching
from MoinMoin.wikiutil import importPlugin, AbsPageName

from graphingwiki.util import filter_categories
from graphingwiki.util import SPECIAL_ATTRS, editable_p
from graphingwiki.util import category_regex, template_regex

CATEGORY_KEY = "gwikicategory"
TEMPLATE_KEY = "gwikitemplate"

# Standard Python operators
OPERATORS = {'<': operator.lt,
             '<=': operator.le,
             '==': operator.eq,
             '!=': operator.ne,
             '>=': operator.ge,
             '>': operator.gt}


def macro_re(macroname):
    return re.compile(r'(?<!#)\s*?\[\[(%s)\((.*?)\)\]\]' % macroname)

metadata_re = macro_re("MetaData")

regexp_re = re.compile('^/.+/$')

# These are the match types for links that really should be noted
linktypes = ["wikiname_bracket", "word",
             "interwiki", "url", "url_bracket"]


def get_revisions(request, page, checkAccess=True):
    pagename = page.page_name
    if checkAccess and not request.user.may.read(pagename):
        return [], []

    parse_text = importPlugin(request.cfg,
                              'action',
                              'savegraphdata',
                              'parse_text')

    alldata = dict()
    revisions = dict()
    
    for rev in page.getRevList():
        revlink = '%s-gwikirevision-%d' % (pagename, rev)

        # Data about revisions is now cached to the graphdata
        # at the same time this is used.
        if request.graphdata.has_key(revlink):
            revisions[rev] = revlink
            continue

        # If not cached, parse the text for the page
        revpage = Page(request, pagename, rev=rev)
        text = revpage.get_raw_body()
        alldata = parse_text(request, revpage, text)
        if alldata.has_key(pagename):
            alldata[pagename].setdefault('meta',
                                         dict())[u'gwikirevision'] = \
                                         [unicode(rev)]
            # Do the cache.
            request.graphdata.cacheset(revlink, alldata[pagename])

            # Add revision as meta so that it is shown in the table
            revisions[rev] = revlink

    pagelist = [revisions[x] for x in sorted(revisions.keys(),
                                             key=ordervalue,
                                             reverse=True)]

    metakeys = set()
    for page in pagelist:
        for key in request.graphdata.get_metakeys(page):
            metakeys.add(key)
    metakeys = sorted(metakeys, key=ordervalue)

    return pagelist, metakeys

PROPERTIES = ['constraint', 'description', 'hint', 'hidden', 'default']


def get_properties(request, pagename):
    properties = dict()
    if pagename:
        if not pagename.endswith('Property'):
            pagename = '%sProperty' % (pagename)
        _, metakeys, _ = metatable_parseargs(request, pagename,
                                             get_all_keys=True)
        properties = get_metas(request, pagename, metakeys)
        for prop in properties:
            if not (prop in PROPERTIES or prop.startswith('color')):
                continue
            properties[prop] = properties[prop][0]

    for prop in PROPERTIES:
        if not prop in properties:
            properties[prop] = ''

    return properties


def getmeta_to_table(input):
    keyoccur = dict()

    keys = list()
    for key in input[0]:
        keyoccur[key] = 1
        keys.append(key)

    for row in input[1:]:
        for i, key in enumerate(row[1:]):
            keylen = len(key)
            if keylen > keyoccur[keys[i]]:
                keyoccur[keys[i]] = keylen

    table_keys = ['Page name']

    for key in input[0]:
        table_keys.extend([key] * keyoccur[key])

    table = [table_keys]

    for vals in input[1:]:
        row = [vals[0]]
        for i, val in enumerate(vals[1:]):
            val.extend([''] * (keyoccur[keys[i]] - len(val)))
            row.extend(val)
        table.append(row)

    return table



def inlinks_key(request, loadedPage, checkAccess=True):
    inLinks = set()
    # Gather in-links regardless of type
    for linktype in loadedPage.get("in", dict()):
        for page in loadedPage['in'][linktype]:
            if checkAccess:
                if not request.user.may.read(page):
                    continue
            inLinks.add((linktype, page))

    inLinks = ['[[%s]]' % (y) for x, y in inLinks]

    return inLinks

# Fetch only the link information for the selected page
def get_links(request, name, metakeys, checkAccess=True, **kw):
    metakeys = set([x for x in metakeys if not '->' in x])
    pageLinks = dict([(key, list()) for key in metakeys])

    loadedPage = request.graphdata.getpage(name)

    loadedOuts = loadedPage.get("out", dict())

    # Add values
    for key in metakeys & set(loadedOuts):
        for value in loadedOuts[key]:
            pageLinks[key].append(value)
            
    return pageLinks

def is_meta_link(value):
    from MoinMoin.parser.text_moin_wiki import Parser

    vals = Parser.scan_re.search(value)
    if not vals:
        return str()

    vals = [x for x, y in vals.groupdict().iteritems() if y]
    for val in vals:
        if val in ['word', 'link', 'transclude', 'url']:
            return 'link'
        if val in ['interwiki', 'email', 'include']:
            return val
    return str()

def metas_to_abs_links(request, page, values):
    new_values = list()
    stripped = False
    for value in values:
        if is_meta_link(value) != 'link':
            new_values.append(value)
            continue
        if ((value.startswith('[[') and value.endswith(']]')) or
            (value.startswith('{{') and value.endswith('}}'))):
            stripped = True
            value = value.lstrip('[')
            value = value.lstrip('{')
        attachment = ''
        for scheme in ('attachment:', 'inline:', 'drawing:'):
            if value.startswith(scheme):
                if len(value.split('/')) == 1:
                    value = ':'.join(value.split(':')[1:])
                    if not '|' in value:
                        # If page does not have descriptive text, try
                        # to shorten the link to the attachment name.
                        value = "%s|%s" % (value.rstrip(']').rstrip('}'), value)
                    value = "%s%s/%s" % (scheme, page, value)
                else:
                    att_page = value.split(':')[1]
                    if (att_page.startswith('./') or
                        att_page.startswith('/') or
                        att_page.startswith('../')):
                        attachment = scheme
                        value = ':'.join(value.split(':')[1:])
        if (value.startswith('./') or
            value.startswith('/') or
            value.startswith('../')):
            value = AbsPageName(page, value)
        if value.startswith('#'):
            value = page + value

        value = attachment + value
        if stripped:
            if value.endswith(']'):
                value = '[[' + value 
            elif value.endswith('}'):
                value = '{{' + value 
        new_values.append(value)

    return new_values


def add_matching_redirs(request, loadedPage, loadedOuts, loadedMeta,
                        metakeys, key, curpage, curkey,
                        prev='', formatLinks=False, linkdata=None):
    if not linkdata:
        linkdata = dict()
    args = curkey.split('->')

    inlink = False
    if args[0] == 'gwikiinlinks':
        inlink = True
        args = args[1:]

    newkey = '->'.join(args[2:])

    last = False

    if not args:
        return
    if len(args) in [1, 2]:
        last = True

    if len(args) == 1:
        linked, target_key = prev, args[0]
    else:
        linked, target_key = args[:2]

    if inlink:
        pages = request.graphdata.get_in(curpage).get(linked, set())
    else:
        pages = request.graphdata.get_out(curpage).get(linked, set())

    for indir_page in set(pages):
        # Relative pages etc
        indir_page = \
            wikiutil.AbsPageName(request.page.page_name,
                                 indir_page)

        if request.user.may.read(indir_page):
            pagedata = request.graphdata.getpage(indir_page)

            outs = pagedata.get('out', dict())
            metas = pagedata.get('meta', dict())

            # Add matches at first round
            if last:
                if target_key in metas:
                    loadedMeta.setdefault(key, list())
                    linkdata.setdefault(key, dict())
                    if formatLinks:
                        values = metas_to_abs_links(
                            request, indir_page, metas[target_key])
                    else:
                        values = metas[target_key]
                    loadedMeta[key].extend(values)
                    linkdata[key].setdefault(indir_page, list()).extend(values)
                else:
                    linkdata.setdefault(key, dict())
                    linkdata[key].setdefault(indir_page, list())
                continue

            elif not target_key in outs:
                continue

            # Handle inlinks separately
            if 'gwikiinlinks' in metakeys:
                inLinks = inlinks_key(request, loadedPage,
                                      checkAccess=checkAccess)

                loadedOuts[key] = inLinks
                continue

            linkdata = add_matching_redirs(request, loadedPage, loadedOuts,
                                           loadedMeta, metakeys, key,
                                           indir_page, newkey, target_key,
                                           formatLinks, linkdata)

    return linkdata


def iter_metas(request, rule, keys=None, checkAccess=True):
    from abusehelper.core import rules, events
    if type(rule) != rules.rules.Match:
        rule = rules.parse(unicode(rule))

    for page, _meta in request.graphdata.items():
        _page = {u"gwikipagename": page}
        metas = _meta.get(u"meta", None)

        if checkAccess and not request.user.may.read(page):
            continue

        if not metas:
            continue

        _out = request.graphdata.get_out(page)
        if _out.has_key('gwikicategory'):
            metas.setdefault(u'gwikicategory', []).extend(_out.get("gwikicategory"))

        data = events.Event(dict(metas.items() + _page.items()))
        if rule.match(data):
            if keys:
                metas = dict((key, metas.get(key, list())) for key in keys)

            yield page, metas


# Fetch metas matching abuse-sa filter rule
def get_metas2(request, rule, keys=None, checkAccess=True):
    results = dict()
    for page, metas in iter_metas(request, rule, keys, checkAccess):
        results[page] = metas

    return results

# Fetch requested metakey value for the given page.
def get_metas(request, name, metakeys, checkAccess=True, 
              includeGenerated=True, formatLinks=False, **kw):
    if not includeGenerated:
        metakeys = [x for x in metakeys if not '->' in x]

    metakeys = set(metakeys)
    pageMeta = dict([(key, list()) for key in metakeys])

    if checkAccess:
        if not request.user.may.read(name):
            return pageMeta

    loadedPage = request.graphdata.getpage(name)

    # Make a real copy of loadedOuts and loadedMeta for tracking indirection
    loadedOuts = dict()
    outs = request.graphdata.get_out(name)
    for key in outs:
        loadedOuts[key] = list(outs[key])

    loadedMeta = dict()
    metas = request.graphdata.get_meta(name)
    for key in metas:
        loadedMeta.setdefault(key, list())
        if formatLinks:
            values = metas_to_abs_links(request, name, metas[key])
        else:
            values = metas[key]
        loadedMeta[key].extend(values)

    loadedOutsIndir = dict()
    for key in loadedOuts:
        loadedOutsIndir.setdefault(key, set()).update(loadedOuts[key])

    if includeGenerated:
        # Handle inlinks separately
        if 'gwikiinlinks' in metakeys:
            inLinks = inlinks_key(request, loadedPage, checkAccess=checkAccess)

            loadedOuts['gwikiinlinks'] = inLinks

        # Meta key indirection support
        for key in metakeys:
            add_matching_redirs(request, loadedPage, loadedOuts, 
                                loadedMeta, metakeys,
                                key, name, key, formatLinks)

    # Add values
    for key in metakeys & set(loadedMeta):
        for value in loadedMeta[key]:
            pageMeta[key].append(value)

    # Add gwikicategory as a special case, as it can be metaedited
    if loadedOuts.has_key('gwikicategory'):
        # Empty (possible) current gwikicategory to fix a corner case
        pageMeta['gwikicategory'] = loadedOuts['gwikicategory']
            
    return pageMeta

def get_pages(request):
    def group_filter(name):
        # aw crap, SystemPagesGroup is not a system page
        if name == 'SystemPagesGroup':
            return False
        if wikiutil.isSystemPage(request, name):
            return False
        return request.user.may.read(name)

    return request.rootpage.getPageList(filter=group_filter)

def edit_meta(request, pagename, oldmeta, newmeta):
    page = PageEditor(request, pagename)

    text = page.get_raw_body()
    text = replace_metas(request, text, oldmeta, newmeta)

    # PageEditor.saveText doesn't allow empty texts
    if not text:
        text = u" "

    try:
        msg = page.saveText(text, 0)
    except page.Unchanged:
        msg = u'Unchanged'

    return msg

def set_metas(request, cleared, discarded, added):
    pages = set(cleared) | set(discarded) | set(added)

    # Discard empties and junk
    pages = [wikiutil.normalize_pagename(x, request.cfg) for x in pages]
    pages = [x for x in pages if x]

    msg = list()

    # We don't have to check whether the user is allowed to read
    # the page, as we don't send any info on the pages out. Only
    # check that we can write to the requested pages.
    for page in pages:
        if not request.user.may.write(page):
            message = "You are not allowed to edit page '%s'" % page
            return False, request.getText(message)

    for page in pages:
        pageCleared = cleared.get(page, set())
        pageDiscarded = discarded.get(page, dict())
        pageAdded = added.get(page, dict())
        
        # Template clears might make sense at some point, not implemented
        if TEMPLATE_KEY in pageCleared:
            pageCleared.remove(TEMPLATE_KEY)
        # Template changes might make sense at some point, not implemented
        if TEMPLATE_KEY in pageDiscarded:
            del pageDiscarded[TEMPLATE_KEY]
        # Save templates for empty pages
        if TEMPLATE_KEY in pageAdded:
            save_template(request, page, ''.join(pageAdded[TEMPLATE_KEY]))
            del pageAdded[TEMPLATE_KEY]

        metakeys = set(pageCleared) | set(pageDiscarded) | set(pageAdded)
        # Filter out uneditables, such as inlinks
        metakeys = editable_p(metakeys)

        old = get_metas(request, page, metakeys, 
                        checkAccess=False, includeGenerated=False)

        new = dict()
        for key in old:
            values = old.pop(key)
            old[key] = values
            new[key] = set(values)
        for key in pageCleared:
            new[key] = set()
        for key, values in pageDiscarded.iteritems():
            for v in values:
                new[key].difference_update(values) 

        for key, values in pageAdded.iteritems():
            new[key].update(values)

        for key, values in new.iteritems():
            ordered = copy.copy(old[key])
            
            for index, value in enumerate(ordered):
                if value not in values:
                    ordered[index] = u""

            values.difference_update(ordered)
            ordered.extend(values)
            new[key] = ordered

        msg.append(edit_meta(request, page, old, new))

    return True, msg

def save_template(request, page, template):
    # Get body, or template if body is not available, or ' '
    raw_body = Page(request, page).get_raw_body()
    msg = ''
    if not raw_body:
        # Start writing

        ## TODO: Add data on template to the text of the saved page?

        raw_body = ' '
        p = PageEditor(request, page)
        template_page = wikiutil.unquoteWikiname(template)
        if request.user.may.read(template_page):
            temp_body = Page(request, template_page).get_raw_body()
            if temp_body:
                raw_body = temp_body

        msg = p.saveText(raw_body, 0)

    return msg

def string_aton(value):
    # Regression: without this, '\d+ ' is an IP according to this func
    if not '.' in value and not ':' in value:
        raise TypeError

    # Support for CIDR notation, eg. 10.10.1.0/24
    end = ''
    if '/' in value:
        value, end = value.split('/', 1)
        end = '/' + end
 
    # 00 is stylistic to avoid this: 
    # >>> sorted(['a', socket.inet_aton('100.2.3.4'), 
    #             socket.inet_aton('1.2.3.4')]) 
    # ['\x01\x02\x03\x04', 'a', 'd\x02\x03\x04'] 
    if '.' in value:
        return u'00' + unicode(socket.inet_pton(socket.AF_INET, 
                                                value).replace('\\', '\\\\'), 
                               "unicode_escape") + end
    else:
        return u'00' + unicode(socket.inet_pton(socket.AF_INET6, 
                                                 value).replace('\\', '\\\\'), 
                               "unicode_escape") + end

def float_parts(part):
    # 2.1.5 should be treated as a float as people seem to expect
    # this.
    part = part.split('.')
    fp = '.'.join(part[:2])
    addon = '.'.join(part[2:])
    if addon:
        addon = '.%s' % (addon)

    fp = float(fp)
    return fp, addon
    
ORDER_FUNCS = [
    # (conversion function, ignored exception type(s)) ipv4
    # addresses. Return values should be unicode strings. The sorting
    # of numbers is currently a bit hacky.
    (lambda x: (string_aton(x), ''), 
     (socket.error, UnicodeEncodeError, TypeError)),
    # integers
    (lambda x: (int(x), ''), ValueError),
    # floats
    (lambda x: float_parts(x), ValueError),
    # strings (unicode or otherwise)
    (lambda x: (x.lower(), ''), AttributeError)
    ]

def ordervalue(value):
    extras = ''
    # treat values prepended with anything accepted by order_funcs:
    # 2.1 blaa => 2.1, [[2.1 blaa]] => 2.1
    if value:
        # Value has already been processed by ordervalue (or faulty
        # data)
        if type(value) not in [str, unicode]:
            return value

        # Strips links syntax and stuff (FIXME does this cover all the
        # relevant cases?)
        value = value.lstrip('[').strip(']')
        value = value.split()

        # Corner case, empty links eg. [[]]
        if not value:
            return ('', '')

        extras = ' '.join(value[1:])
        value = value[0]
    for func, ignoredExceptionTypes in ORDER_FUNCS:
        try:
            out, addon = func(value)
            return (out, addon + extras)
        except ignoredExceptionTypes:
            pass
    return value

# You can implement different coordinate formats here
COORDINATE_REGEXES = [
    # long, lat -> to itself
    ('(-?\d+\.\d+,-?\d+\.\d+)', lambda x: x.group())
    ]
def verify_coordinates(coords):
    for regex, replacement in COORDINATE_REGEXES:
        if re.match(regex, coords):
            try:
                retval = re.sub(regex, replacement, coords)
                return retval
            except:
                pass

def _metatable_parseargs(request, args, cat_re, temp_re):

    # Arg placeholders
    argset = set([])
    keyspec = list()
    excluded_keys = list()
    orderspec = list()
    limitregexps = dict()
    limitops = dict()

    # Capacity for storing indirection keys in metadata comparisons
    # and regexps, eg. k->c=/.+/
    indirection_keys = list()

    # list styles
    styles = dict()

    # Flag: were there page arguments?
    pageargs = False

    # Regex preprocessing
    for arg in (x.strip() for x in args.split(',') if x.strip()):
        # metadata key spec, move on
        if arg.startswith('||') and arg.endswith('||'):
            # take order, strip empty ones, look at styles
            for key in arg.split('||'):
                if not key:
                    continue
                # Grab styles
                if key.startswith('<') and '>' in key:
                    style = wikiutil.parseAttributes(request,
                                                     key[1:], '>')
                    key = key[key.index('>') + 1:].strip()

                    if style:
                        styles[key] = style[0]

                # Grab key exclusions
                if key.startswith('!'):
                    excluded_keys.append(key.lstrip('!'))
                    continue
                    
                keyspec.append(key.strip())

            continue

        op_match = False
        # Check for Python operator comparisons
        for op in OPERATORS:
            if op in arg:
                data = arg.rsplit(op)
                
                # If this is not a comparison but indirection,
                # continue. Good: k->s>3, bad: k->s=/.+/
                if op == '>' and data[0].endswith('-'):
                    continue

                # Must have real comparison
                if not len(data) == 2:
                    if op == '==':
                        data.append('')
                    else:
                        continue

                key, comp = map(string.strip, data)

                # Add indirection key
                if '->' in key:
                    indirection_keys.append(key)

                limitops.setdefault(key, list()).append((comp, op))
                op_match = True

            # One of the operators matched, no need to go forward
            if op_match:
                break

        # One of the operators matched, process next arg
        if op_match:
            continue

        # Metadata regexp, move on
        if '=' in arg:
            data = arg.split("=")
            key = data[0]

            # Add indirection key
            if '->' in key:
                indirection_keys.append(key)

            val = '='.join(data[1:])

            # Assume that value limits are regexps, if
            # not, escape them into exact regexp matches
            if not regexp_re.match(val):
                from MoinMoin.parser.text_moin_wiki import Parser

                # If the value is a page, make it a non-matching
                # regexp so that all link variations will generate a
                # match. An alternative would be to match from links
                # also, but in this case old-style metalinks, which
                # cannot be edited, would appear in metatables, which
                # is not wanted (old-style eg. [[Page| key: Page]])

                # Only allow non-matching regexp for values if they
                # are WikiWords. Eg. 'WikiWord some text' would match
                # 'WikiWord', emulating ye olde matching behaviour,
                # but 'nonwikiword some text' would not match
                # 'nonwikiword'
                if re.match(Parser.word_rule_js, val):
                    re_val = "(%s|" % (re.escape(val)) 
                else:
                    re_val = "(^%s$|" % (re.escape(val)) 
                # or as bracketed link
                re_val += "(?P<sta>\[\[)%s(?(sta)\]\])|" % (re.escape(val)) 

                # or as commented bracketed link
                re_val += "(?P<stb>\[\[)%s(?(stb)\|[^\]]*\]\]))" % \
                    (re.escape(val)) 
                
                limitregexps.setdefault(
                    key, set()).add(re.compile(re_val, re.UNICODE))

            # else strip the //:s
            else:
                if len(val) > 1:
                    val = val[1:-1]

                limitregexps.setdefault(
                    key, set()).add(re.compile(val, 
                                               re.IGNORECASE | re.UNICODE))
            continue

        # order spec
        if arg.startswith('>>') or arg.startswith('<<'):
            # eg. [('<<', 'koo'), ('>>', 'kk')]
            orderspec = re.findall('(?:(<<|>>)([^<>]+))', arg)
            continue

        # Ok, we have a page arg, i.e. a page or page regexp in args
        pageargs = True

        # Normal pages, check perms, encode and move on
        if not regexp_re.match(arg):
            # Fix relative links
            if (arg.startswith('/') or arg.startswith('./') or
                arg.startswith('../')):
                arg = wikiutil.AbsPageName(request.page.page_name, arg)

            argset.add(arg)
            continue

        # Ok, it's a page regexp

        # if there's something wrong with the regexp, ignore it and move on
        try:
            arg = arg[1:-1]
            # Fix relative links
            if (arg.startswith('/') or arg.startswith('./') or
                arg.startswith('../')):
                arg = wikiutil.AbsPageName(request.page.page_name, arg)

            page_re = re.compile("%s" % arg)
        except:
            continue

        # Get all pages, check which of them match to the supplied regexp
        for page in request.graphdata:
            if page_re.match(page):
                argset.add(page)

    return (argset, pageargs, keyspec, excluded_keys, orderspec, 
            limitregexps, limitops, indirection_keys, styles)

def metatable_parseargs(request, args,
                        get_all_keys=False,
                        get_all_pages=False,
                        checkAccess=True,
                        include_unsaved=False,
                        parsefunc=_metatable_parseargs):
    if not args:
        # If called from a macro such as MetaTable,
        # default to getting the current page
        req_page = request.page
        if get_all_pages or req_page is None or req_page.page_name is None:
            args = ""
        else:
            args = req_page.page_name

    # Category, Template matching regexps
    cat_re = category_regex(request)
    temp_re = template_regex(request)

    argset, pageargs, keyspec, excluded_keys, orderspec, \
        limitregexps, limitops, indirection_keys, styles = \
        parsefunc(request, args, cat_re, temp_re)

    # If there were no page args, default to all pages
    if not pageargs and not argset:
        pages = request.graphdata.pagenames()
    else:
        pages = set()
        categories = set(filter_categories(request, argset))
        other = argset - categories

        for arg in categories:
            newpages = request.graphdata.get_in(arg).get(CATEGORY_KEY, list())

            for newpage in newpages:
                # Check that the page is not a category or template page
                if cat_re.search(newpage) or temp_re.search(newpage):
                    continue
                pages.add(newpage)

        pages.update(other)

    pagelist = set()
    for page in pages:
        clear = True
        # Filter by regexps (if any)
        if limitregexps:
            # We're sure we have access to read the page, don't check again
            metas = get_metas(request, page, limitregexps, checkAccess=False)

            for key, re_limits in limitregexps.iteritems():

                values = metas[key]
                if not values:
                    clear = False
                    break

                for re_limit in re_limits:
                    clear = False

                    # Iterate all the keys for the value for a match
                    for value in values:
                        if re_limit.search(value):

                            clear = True
                            # Single match is enough
                            break

                    # If one of the key's regexps did not match
                    if not clear:
                        break

                # If all of the regexps for a single page did not match
                if not clear:
                    break

        if not clear:
            continue

        if limitops:
            # We're sure we have access to read the page, don't check again
            metas = get_metas(request, page, limitops, checkAccess=False)

            for key, complist in limitops.iteritems():
                values = metas[key]

                for (comp, op) in complist:
                    clear = False

                    # The non-existance of values is good for not
                    # equal, bad for the other comparisons
                    if not values:
                        if op == '!=':
                            clear = True
                            continue
                        elif op == '==' and not comp:
                            clear = True
                            continue

                    # Must match any
                    for value in values:
                        value, comp = ordervalue(value), ordervalue(comp)

                        if OPERATORS[op](value, comp):
                            clear = True
                            break

                    # If one of the comparisons for a single key were not True
                    if not clear:
                        break

                # If all of the comparisons for a single page were not True
                if not clear:
                    break
                            
        # Add page if all the regexps and operators have matched
        if clear:
            pagelist.add(page)

    # Filter to saved pages that can be read by the current user
    def is_saved(name):
        if include_unsaved:
            return True
        return request.graphdata.is_saved(name)

    def can_be_read(name):
        return request.user.may.read(name)

    # Only give saved pages
    pagelist = filter(is_saved, pagelist)
    # Only give pages that can be read by the current user
    if checkAccess:
        pagelist = filter(can_be_read, pagelist)

    metakeys = set([])
    if not keyspec:
        for name in pagelist:
            # MetaEdit wants all keys by default
            if get_all_keys:
                for key in request.graphdata.get_metakeys(name):
                    metakeys.add(key)
            else:
                # For MetaTable etc
                for key in (x for x in request.graphdata.get_metakeys(name)
                            if not x in SPECIAL_ATTRS):
                    metakeys.add(key)

        # Add gathered indirection metakeys
        metakeys.update(indirection_keys)

        # Exclude keys
        for key in excluded_keys:
            metakeys.discard(key)

        metakeys = sorted(metakeys, key=ordervalue)
    else:
        metakeys = keyspec

    # sorting pagelist
    if not orderspec:
        pagelist = sorted(pagelist, key=ordervalue)
    else:
        orderkeys = [key for (direction, key) in orderspec]
        orderpages = dict()

        for page in pagelist:
            ordermetas = get_metas(request, page, orderkeys, checkAccess=False)
            for key, values in ordermetas.iteritems():
                values = map(ordervalue, values)
                ordermetas[key] = values
            orderpages[page] = ordermetas

        def comparison(page1, page2):
            for direction, key in orderspec:
                reverse = False
                if direction == ">>":
                    reverse = True

                if key == "gwikipagename":
                    values1 = [page1]
                    values2 = [page2]
                else:
                    values1 = sorted(orderpages[page1][key], reverse=reverse)
                    values2 = sorted(orderpages[page2][key], reverse=reverse)
            
                result = cmp(values1, values2)
                if result == 0:
                    continue
            
                if not values1:
                    return 1
                if not values2:
                    return -1

                if reverse:
                    return -result
                return result
            return cmp(ordervalue(page1), ordervalue(page2))

        pagelist = sorted(pagelist, cmp=comparison)

    return pagelist, metakeys, styles

def check_attachfile(request, pagename, aname):
    # Check that the attach dir exists
    getAttachDir(request, pagename, create=1)
    aname = wikiutil.taintfilename(aname)
    fpath = getFilename(request, pagename, aname)

    # Trying to make sure the target is a regular file
    if os.path.isfile(fpath) and not os.path.islink(fpath):
        return fpath, True

    return fpath, False

def save_attachfile(request, pagename, content, aname, 
                    overwrite=False, log=False):
    try:
        fpath, exists = check_attachfile(request, pagename, aname)
        if not overwrite and exists:
            return False

        # Save the data to a file under the desired name
        stream = open(fpath, 'wb')
        stream.write(content)
        stream.close()

        if log:
            _addLogEntry(request, 'ATTNEW', pagename, aname)
    except:
        return False

    return True

def load_attachfile(request, pagename, aname):
    try:
        fpath, exists = check_attachfile(request, pagename, aname)
        if not exists:
            return None

        # Load the data from the file
        stream = open(fpath, 'rb')
        adata = stream.read()
        stream.close()
    except:
        return None

    return adata

def delete_attachfile(request, pagename, aname, log=False):
    try:
        fpath, exists = check_attachfile(request, pagename, aname)
        if not exists:
            return False

        os.unlink(fpath)

        if log:
            _addLogEntry(request, 'ATTDEL', pagename, aname)
    except:
        return False

    return True

def list_attachments(request, pagename):
    # Code from MoinMoin/action/AttachFile._get_files
    attach_dir = getAttachDir(request, pagename)
    if os.path.isdir(attach_dir):
        files = map(lambda a: a.decode(config.charset), os.listdir(attach_dir))
        files.sort()
        return files

    return []

# FIXME this should probably include all the formatters beyond the
# default install. The problem is that there does not seem to be a
# good way for listing them. However, in testing, I did not find a way
# to cache the output of the other formatters by just using the wiki,
# so already this could work for most cases.
CACHE_AUTOMATED = ['pagelinks', 'text_html', 'text_html_percent',
                   'dom_xml', 'text_plain', 'text_docbook', 'text_gedit',
                   'text_python', 'text_xml']

# Caching functions for items in the page cache, should they be needed
# in other code. Sendcache manipulation functions can be found in
# util.
def check_pagecachefile(request, pagename, cfname):
    page = Page(request, pagename)
    data_cache = caching.CacheEntry(request, page, cfname, 
                                    scope='item', do_locking=True)
    return data_cache, data_cache.exists()

def save_pagecachefile(request, pagename, content, cfname, overwrite=False):
    try:
        entry, exists = check_pagecachefile(request, pagename, cfname)
        if not overwrite and exists:
            return False

        # Do not save over MoinMoin autogenerated page cache files,
        # having arbitrary data there will probably only result in
        # crashes. Deleting these files is ok though.
        if cfname in CACHE_AUTOMATED:
            return False

        # Save the data to a file under the desired name
        entry.open(mode='wb')
        entry.write(content)
        entry.close()
    except caching.CacheError:
        return False

    return True


def load_pagecachefile(request, pagename, cfname):
    try:
        entry, exists = check_pagecachefile(request, pagename, cfname)
        if not exists:
            return None

        # Load data from the cache file
        entry.open(mode='rb')
        cfdata = entry.read()
        entry.close()
    except caching.CacheError:
        return None

    return cfdata


def delete_pagecachefile(request, pagename, cfname):
    try:
        entry, exists = check_pagecachefile(request, pagename, cfname)
        if not exists:
            return False

        entry.remove()
    except caching.CacheError:
        return False

    return True


def list_pagecachefiles(request, pagename):
    page = Page(request, pagename)
    return caching.get_cache_list(request, page, 'item')


def _doctest_request(graphdata=dict(), mayRead=True, mayWrite=True):
    class Request(object):
        pass

    class Config(object):
        pass

    class Object(object):
        pass

    class Cache(object):
        pass

    class GraphData(dict):
        def getpage(self, page):
            return self.get(page, dict())
    
    request = Request()
    request.cfg = Config()
    request.cfg.cache = Cache()
    request.cfg.cache.page_category_regex = category_regex(request)
    request.cfg.cache.page_category_regexact = category_regex(request, act=True)
    request.graphdata = GraphData(graphdata)

    request.user = Object()
    request.user.may = Object()
    request.user.may.read = lambda x: mayRead
    request.user.may.write = lambda x: mayWrite

    return request


def _test():
    import doctest
    doctest.testmod()

if __name__ == "__main__":
    _test()
