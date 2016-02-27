# -*- coding: utf-8 -*-"
"""
    class for handling page metadata

    @copyright: 2006-2016 by Jussi Eronen <exec@iki.fi>
"""
import os
import operator
import socket

from time import time

from MoinMoin.wikiutil import get_processing_instructions, AbsPageName
from MoinMoin.Page import LinkCollectingPage
from MoinMoin import config
from MoinMoin import caching
from MoinMoin.parser.link_collect import Parser as lcparser

from util import (regexp_re, filter_categories, category_regex, 
                  template_regex, node_type, SPECIAL_ATTRS, NO_TYPE)
from wikitextutil import parse_categories, parse_text

# Standard Python operators
OPERATORS = {'<': operator.lt,
             '<=': operator.le,
             '==': operator.eq,
             '!=': operator.ne,
             '>=': operator.ge,
             '>': operator.gt}

def savegraphdata(pagename, request, text, pagedir, pageitem):
    try:
        # Skip MoinEditorBackups
        if pagename.endswith('/MoinEditorBackup'):
            return

        # parse_text, add_link, add_meta return dict with keys like
        # 'BobPerson' -> {u'out': {'friend': ['GeorgePerson']}}
        # (ie. same as what graphdata contains)

        # Get new data from parsing the page
        new_data = parse_text(request, pageitem, text)

        request.graphdata.set_page(request, pagename, new_data)

        ## Remove deleted pages from the backend
        # 1. Removing data at the moment of deletion
        # Deleting == saving a revision with the text 'deleted/n', then 
        # removing the revision. This seems to be the only way to notice.
        if text == 'deleted\n':
            request.graphdata.clear_page(request, pagename)
        else:
            # 2. Removing data when rehashing. 
            # New pages do not exist, but return a revision of 99999999 ->
            # Check these both to avoid deleting new pages.
            pf, rev, exists = pageitem.get_rev() 
            if rev != 99999999:
                if not exists:
                    _clear_page(request, pagename)

        pageitem.delete_caches()
        request.graphdata.post_save(pagename)
    except:
        request.graphdata.abort()
        raise

def underlay_to_pages(req, p):
    underlaydir = req.cfg.data_underlay_dir

    pagepath = p.getPagePath()

    # If the page has not been created yet, create its directory and
    # save the stuff there
    if underlaydir in pagepath:
        pagepath = pagepath.replace(underlaydir, pagepath)
        if not os.path.exists(pagepath):
            os.makedirs(pagepath)

    return pagepath

# Functions for properly opening, closing, saving and deleting
# graphdata.
def graphdata_getter(self):
#    from graphingwiki.backend.couchdbclient import GraphData
#    from graphingwiki.backend.durusclient import GraphData
    from MoinMoin.metadata.backend.shelvedb import GraphData
    if "_graphdata" not in self.__dict__:
        dbconfig = getattr(self.cfg, 'dbconfig', {})
        if "dbname" not in dbconfig:
            dbconfig["dbname"] = self.cfg.interwikiname

        self.__dict__["_graphdata"] = GraphData(self, **dbconfig)
    return self.__dict__["_graphdata"]

def graphdata_close(self):
    graphdata = self.__dict__.pop("_graphdata", None)
    if graphdata is not None:
        graphdata.commit()
        graphdata.close()

def graphdata_commit(self, *args):
    graphdata = self.__dict__.pop("_graphdata", None)
    if graphdata is not None:
        graphdata.commit()

## XXX: Hook PageEditor.sendEditor to add data on template to the
## text of the saved page?
def graphdata_save(page):
    text = page.get_raw_body()
    path = underlay_to_pages(page.request, page)

    savegraphdata(page.page_name, page.request, text, path, page)

def graphdata_copy(page, newpagename):
    text = page.get_raw_body()
    path = underlay_to_pages(page.request, page)

    savegraphdata(newpagename, page.request, text, path, page)

# Note: PageEditor.renamePage seems to use .saveText for the new
# page (thus already updating the page's metas), so only the old page's
# metas need to be deleted explicitly.
def graphdata_rename(page):
    path = underlay_to_pages(page.request, page)

    # Rename is really filesystem-level rename, no old data is really
    # left behind, so it should be cleared.  When saving with text
    # 'deleted\n', no graph data is actually saved.
    savegraphdata(page.page_name, page.request, 'deleted\n', path, page)

    # Rename might litter empty directories data/pagename and
    # data/pagename/cache, let's remove them
    oldpath = page.getPagePath(check_create=0)
    for dirpath, dirs, files in os.walk(oldpath, topdown=False):
        # If there are files left, some backups etc information is
        # still there, so let's quit
        if files:
            break

        os.rmdir(dirpath)

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
        indir_page = wikiutil.AbsPageName(request.page.page_name,
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
