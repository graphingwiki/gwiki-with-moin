# -*- coding: utf-8 -*-"
import re

from util import filter_categories

DEFAULT_META_BEFORE = '^----'

# Dl_re includes newlines, if available, and will replace them
# in the sub-function
DL_RE = re.compile('(^\s+(.+?):: (.+)$\n?)', re.M)
# From Parser, slight modification due to multiline usage
DL_PROTO_RE = re.compile('(^\s+(.+?)::\s*$\n?)', re.M)

SEPARATOR = '-gwikiseparator-'

def parse_text(request, page, text):
    pagename = page.page_name
    
    newreq = request
    newreq.page = lcpage = LinkCollectingPage(newreq, pagename, text)
    parserclass = lcparser
    myformatter = importPlugin(request.cfg, "formatter",
                               'nullformatter', "Formatter")
    lcpage.formatter = myformatter(newreq)
    lcpage.formatter.page = lcpage
    p = parserclass(lcpage.get_raw_body(), newreq, formatter=lcpage.formatter)
    lcpage.parser = p
    lcpage.format(p)
    
    # These are the match types that really should be noted
    linktypes = ["wikiname_bracket", "word",                  
                 "interwiki", "url", "url_bracket"]
    
    new_data = dict_with_getpage()

    # Add the page categories as links too
    categories, _, _ = parse_categories(request, text)

    # Process ACL:s
    pi, _ = get_processing_instructions(text)
    for verb, args in pi:
        if verb == u'acl':
            # Add all ACL:s on multiple lines to an one-lines
            acls = new_data.get(pagename, dict()).get('acl', '')
            acls = acls.strip() + args
            new_data.setdefault(pagename, dict())['acl'] = acls

    for metakey, value in p.definitions.iteritems():
        for ltype, item in value:
            dnode = None

            if  ltype in ['url', 'wikilink', 'interwiki', 'email']:
                dnode = item[1]
                if '#' in dnode:
                    # Fix anchor links to point to the anchor page
                    url = False
                    for schema in config.url_schemas:
                        if dnode.startswith(schema):
                            url = True
                    if not url:
                        # Do not fix URLs
                        if dnode.startswith('#'):
                            dnode = pagename
                        else:
                            dnode = dnode.split('#')[0]
                if (dnode.startswith('/') or
                    dnode.startswith('./') or
                    dnode.startswith('../')):
                    # Fix relative links
                    dnode = AbsPageName(pagename, dnode)

                hit = item[0]
            elif ltype == 'category':
                # print "adding cat", item, repr(categories)
                dnode = item
                hit = item
                if item in categories:
                    add_link(new_data, pagename, dnode, 
                             u"gwikicategory")
            elif ltype == 'meta':
                add_meta(new_data, pagename, (metakey, item))
            elif ltype == 'include':
                # No support for regexp includes, for now!
                if not item[0].startswith("^"):
                    included = AbsPageName(pagename, item[0])
                    add_link(new_data, pagename, included, u"gwikiinclude")

            if dnode:
                add_link(new_data, pagename, dnode, metakey)

    return new_data

def parse_categories(request, text):
    r"""
    Parse category names from the page. Return a list of parsed categories,
    list of the preceding text lines and a list of the lines with categories.

    >>> request = _doctest_request()
    >>> parse_categories(request, "CategoryTest")
    (['CategoryTest'], [], ['CategoryTest'])

    Take into account only the categories that come after all other text
    (excluding whitespaces):

    >>> parse_categories(request, "Blah\nCategoryNot blah\nCategoryTest\n")
    (['CategoryTest'], ['Blah', 'CategoryNot blah'], ['CategoryTest', ''])

    The line lists are returned in a way that the original text can be
    easily reconstructed from them.

    >>> original_text = "Blah\nCategoryNot blah\n--------\nCategoryTest\n"
    >>> _, head, tail = parse_categories(request, original_text)
    >>> tail[0] == "--------"
    True
    >>> "\n".join(head + tail) == original_text
    True

    >>> original_text = "Blah\nCategoryNot blah\nCategoryTest\n"
    >>> _, head, tail = parse_categories(request, original_text)
    >>> "\n".join(head + tail) == original_text
    True

    Regression test, bug #540: Pages with only categories (or whitespaces) 
    on several lines don't get parsed correctly:

    >>> parse_categories(request, "\nCategoryTest")
    (['CategoryTest'], [''], ['CategoryTest'])
    """

    other_lines = text.splitlines()
    if text.endswith("\n"):
        other_lines.append("")

    categories = list()
    category_lines = list()
    unknown_lines = list()

    # Start looking at lines from the end to the beginning
    while other_lines:
        if not other_lines[-1].strip() or other_lines[-1].startswith("##"):
            unknown_lines.insert(0, other_lines.pop())
            continue

        # TODO: this code is broken, will not work for extended links
        # categories, e.g ["category hebrew"]
        candidates = other_lines[-1].split()
        confirmed = filter_categories(request, candidates)

        # A category line is defined as a line that contains only categories
        if len(confirmed) < len(candidates):
            # The line was not a category line
            break

        categories.extend(confirmed)
        category_lines[:0] = unknown_lines
        category_lines.insert(0, other_lines.pop())
        unknown_lines = list()

    if other_lines and re.match("^\s*-{4,}\s*$", other_lines[-1]):
        category_lines[:0] = unknown_lines
        category_lines.insert(0, other_lines.pop())
    else:
        other_lines.extend(unknown_lines)
    return categories, other_lines, category_lines

def edit_categories(request, savetext, action, catlist):
    """
    >>> request = _doctest_request()
    >>> s = "= @PAGE@ =\\n" + \
        "[[TableOfContents]]\\n" + \
        "[[LinkedIn]]\\n" + \
        "----\\n" + \
        "CategoryIdentity\\n" +\
        "##fslsjdfldfj\\n" +\
        "CategoryBlaa\\n"
    >>> edit_categories(request, s, 'add', ['CategoryEi'])
    u'= @PAGE@ =\\n[[TableOfContents]]\\n[[LinkedIn]]\\n----\\nCategoryBlaa CategoryIdentity CategoryEi\\n'
    >>> edit_categories(request, s, 'set', ['CategoryEi'])
    u'= @PAGE@ =\\n[[TableOfContents]]\\n[[LinkedIn]]\\n----\\nCategoryEi\\n'
    >>> s = "= @PAGE@ =\\n" + \
       "[[TableOfContents]]\\n" + \
       "[[LinkedIn]]\\n" + \
       "----\\n" + \
       "## This is not a category line\\n" +\
       "CategoryIdentity hlh\\n" +\
       "CategoryBlaa\\n"
    >>>
    >>> edit_categories(request, s, 'add', ['CategoryEi'])
    u'= @PAGE@ =\\n[[TableOfContents]]\\n[[LinkedIn]]\\n----\\n## This is not a category line\\nCategoryIdentity hlh\\n----\\nCategoryBlaa CategoryEi\\n'
    >>> edit_categories(request, s, 'set', ['CategoryEi'])
    u'= @PAGE@ =\\n[[TableOfContents]]\\n[[LinkedIn]]\\n----\\n## This is not a category line\\nCategoryIdentity hlh\\n----\\nCategoryEi\\n'
    """

    # Filter out anything that is not a category
    catlist = filter_categories(request, catlist)
    confirmed, lines, _ = parse_categories(request, savetext)

    # Remove the empty lines from the end
    while lines and not lines[-1].strip():
        lines.pop()

    # Check out which categories we are going to write back
    if action == "set":
        categories = list(catlist)
    elif action == "del":
        categories = list(confirmed)
        for category in catlist:
            if category in categories:
                categories.remove(category)
    else:
        categories = list(confirmed)
        for category in catlist:
            if category not in categories:
                categories.append(category)

    if categories:
        lines.append(u"----")
        lines.append(" ".join(categories))

    return u"\n".join(lines) + u"\n"

def remove_preformatted(text):
    # Before setting metas, remove preformatted areas
    preformatted_re = re.compile('((^ [^:]+?:: )?({{{[^{]*?}}}))', re.M|re.S)
    wiki_preformatted_re = re.compile('{{{\s*\#\!wiki', re.M|re.S)

    keys_to_markers = dict()
    markers_to_keys = dict()

    # Replace with unique format strings per preformatted area
    def replace_preformatted(mo):
        key, preamble, rest = mo.groups()

        # Cases 594, 596, 759: ignore preformatted section starting on
        # the metakey line
        if preamble:
            return key

        # Do not remove wiki-formatted areas, we need the keys in them
        if wiki_preformatted_re.search(key):
            return key

        # All other areas should be removed
        marker = "%d-%s" % (mo.start(), md5(repr(key)).hexdigest())
        while marker in text:
            marker = "%d-%s" % (mo.start(), md5(marker).hexdigest())

        keys_to_markers[key] = marker
        markers_to_keys[marker] = key

        return marker

    text = preformatted_re.sub(replace_preformatted, text)

    return text, keys_to_markers, markers_to_keys

def add_meta_regex(request, inclusion, newval, oldtext):
    """
    >>> request = _doctest_request()
    >>> s = "= @PAGE@ =\\n" + \
        "[[TableOfContents]]\\n" + \
        "[[LinkedIn]]\\n" + \
        "----\\n" + \
        "CategoryIdentity\\n" +\
        "##fslsjdfldfj\\n" +\
        "CategoryBlaa\\n"
    >>> 
    >>> add_meta_regex(request, u' ööö ää:: blaa', u'blaa', s)
    u'= @PAGE@ =\\n[[TableOfContents]]\\n[[LinkedIn]]\\n \\xc3\\xb6\\xc3\\xb6\\xc3\\xb6 \\xc3\\xa4\\xc3\\xa4:: blaa\\n----\\nCategoryIdentity\\n##fslsjdfldfj\\nCategoryBlaa\\n'
    >>> 
    >>> request.cfg.gwiki_meta_after = '^----'
    >>> 
    >>> add_meta_regex(request, u' ööö ää:: blaa', u'blaa', s)
    u'= @PAGE@ =\\n[[TableOfContents]]\\n[[LinkedIn]]\\n----\\n \\xc3\\xb6\\xc3\\xb6\\xc3\\xb6 \\xc3\\xa4\\xc3\\xa4:: blaa\\nCategoryIdentity\\n##fslsjdfldfj\\nCategoryBlaa\\n'
    >>> 
    >>> s = '\\n'.join(s.split('\\n')[:2])
    >>> 
    >>> add_meta_regex(request, u' ööö ää:: blaa', u'blaa', s)
    u'= @PAGE@ =\\n[[TableOfContents]]\\n \\xc3\\xb6\\xc3\\xb6\\xc3\\xb6 \\xc3\\xa4\\xc3\\xa4:: blaa\\n'
    """

    if not newval:
        return oldtext

    # print "Add", repr(newval), repr(oldmeta.get(key, ''))

    # patterns after or before of which the metadata
    # should be included
    pattern = getattr(request.cfg, 'gwiki_meta_after', '')
    repl_fun = lambda m: m.group(1) + '\n' + inclusion
    if not pattern:
        pattern = getattr(request.cfg, 'gwiki_meta_before', '')
        repl_fun = lambda m: inclusion + '\n' + m.group(1)
    if not pattern:
        pattern = DEFAULT_META_BEFORE

    # if pattern is not found on page, just append meta
    pattern_re = re.compile("(%s)" % (pattern), re.M|re.S)
    newtext, repls = pattern_re.subn(repl_fun, oldtext, 1)
    if not repls:
        oldtext = oldtext.strip('\n')
        oldtext += '\n%s\n' % (inclusion)
    else:
        oldtext = newtext

    return oldtext

def replace_metas(request, text, oldmeta, newmeta):
    r"""
    >>> request = _doctest_request()

    Replacing metas:
    >>> replace_metas(request,
    ...               u" test:: 1\n test:: 2",
    ...               dict(test=[u"1"]),
    ...               dict(test=[u"3"]))
    u' test:: 3\n test:: 2\n'
    >>> replace_metas(request,
    ...               u" test:: 1\n test:: 2",
    ...               dict(test=[u"1"]),
    ...               dict(test=[u""]))
    u' test:: 2\n'
    >>> replace_metas(request,
    ...               u" test:: 1\n test:: 2",
    ...               dict(test=[u"2"]),
    ...               dict(test=[u""]))
    u' test:: 1\n'

    Prototypes:
    >>> replace_metas(request,
    ...               u"This is just filler\n test::\nYeah",
    ...               dict(),
    ...               dict(test=[u"1"]))
    u'This is just filler\n test:: 1\nYeah\n'

    Adding metas, clustering when possible:
    >>> replace_metas(request,
    ...               u"This is just filler\nYeah",
    ...               dict(test=[]),
    ...               dict(test=[u"1", u"2"]))
    u'This is just filler\nYeah\n test:: 1\n test:: 2\n'
    >>> replace_metas(request,
    ...               u"This is just filler\n test:: 1\nYeah",
    ...               dict(test=[u"1"]),
    ...               dict(test=[u"1", u"2"]))
    u'This is just filler\n test:: 2\n test:: 1\nYeah\n'
    >>> replace_metas(request,
    ...               u"This is just filler\n test:: 2\n test:: 1\nYeah",
    ...               dict(test=[u"1", u"2"]),
    ...               dict(test=[u"1", u"2", u"3"]))
    u'This is just filler\n test:: 3\n test:: 2\n test:: 1\nYeah\n'

    Handling the magical duality normal categories (CategoryBah) and
    meta style categories. If categories in metas are actually valid
    according to category regexp, retain them as Moin-style
    categories. Otherwise, delete them.

    >>> replace_metas(request,
    ...               u"",
    ...               dict(),
    ...               dict(gwikicategory=[u"test"]))
    u'\n'
    >>> replace_metas(request,
    ...               u"",
    ...               dict(),
    ...               dict(gwikicategory=[u"CategoryTest"]))
    u'----\nCategoryTest\n'
    >>> replace_metas(request,
    ...               u" gwikicategory:: test",
    ...               dict(gwikicategory=[u"test"]),
    ...               dict(gwikicategory=[u"CategoryTest"]))
    u'----\nCategoryTest\n'
    >>> replace_metas(request,
    ...               u"CategoryTest",
    ...               dict(gwikicategory=[u"CategoryTest"]),
    ...               dict(gwikicategory=[u"CategoryTest2"]))
    u'----\nCategoryTest2\n'

    Regression test: The following scenario probably shouldn't produce
    an empty result text.
    
    >>> replace_metas(request,
    ...               u" test:: 1\n test:: 1", 
    ...               dict(test=[u"1", u"1"]),
    ...               dict(test=[u"1", u""]))
    u' test:: 1\n'

    Regression test empty categories should not be saved.

    >>> replace_metas(request,
    ...               u" test:: 1\n----\nCategoryFoo", 
    ...               {u'gwikicategory': [u'CategoryFoo']},
    ...               {u'gwikicategory': [u' ']})
    u' test:: 1\n'

    Regression on a metaformedit bug
    
    >>> replace_metas(request,
    ...               u' aa:: k\n ab:: a\n ab:: a\n----\nCategoryFoo\n',
    ...               {u'aa': [u'k'], u'ab': [u'a', u'a']},
    ...               {u'aa': [u'k'], u'ab': [u'', u'', u' ']})
    u' aa:: k\n----\nCategoryFoo\n'

    Regression test, bug #527: If the meta-to-be-replaced is not
    the first one on the page, it should still be replaced.
    
    >>> replace_metas(request,
    ...               u" bar:: 1\n foo:: 2",
    ...               dict(foo=[u"2"]),
    ...               dict(foo=[u""]))
    u' bar:: 1\n'

    Regression test, bug #594: Metas with preformatted values caused
    corruption.
    
    >>> replace_metas(request,
    ...               u" foo:: {{{a}}}\n",
    ...               dict(foo=[u"{{{a}}}"]),
    ...               dict(foo=[u"b"]))
    u' foo:: b\n'

    Regression test, bug #596: Replacing with empty breaks havoc

    >>> replace_metas(request,
    ...               u" a:: {{{}}}\n b:: {{{Password}}}",
    ...               {'a': [u'{{{}}}']},
    ...               {'a': [u'']})
    u' b:: {{{Password}}}\n'

    Regression test, bug #591 - empties erased

    >>> replace_metas(request,
    ...               u"blaa\n  a:: \n b:: \n c:: \n",
    ...               {u'a': [], u'c': [], u'b': []},
    ...               {u'a': [u'', u' '], u'c': [u'', u' '], u'b': [u'a', u' ']})
    u'blaa\n a:: \n b:: a\n c::\n'

    replace_metas(request, 
    ...           u' status:: open\n agent:: 127.0.0.1-273418929\n heartbeat:: 1229625387.57',
    ...           {'status': [u'open'], 'heartbeat': [u'1229625387.57'], 'agent': [u'127.0.0.1-273418929']},
    ...           {'status': [u'', 'pending'], 'heartbeat': [u'', '1229625590.17'], 'agent': [u'', '127.0.0.1-4124520965']})
    u' status:: pending\n heartbeat:: 1229625590.17\n agent:: 127.0.0.1-4124520965\n'

    Regression test, bug #672
    >>> replace_metas(request,
    ...               u'<<MetaTable(Case672/A, Case672/B, Case672/C)>>\n\n test:: a\n',
    ...               {u'test': [u'a']},
    ...               {u'test': [u'a', u'']})
    u'<<MetaTable(Case672/A, Case672/B, Case672/C)>>\n\n test:: a\n'

    Regression test, bug #739
    >>> replace_metas(request,
    ...               u' a:: k\n{{{\n#!wiki comment\n}}}\n b:: \n',
    ...               {'a': [u'k'], 'gwikicategory': []},
    ...               {'a': [u'', 'b'], 'gwikicategory': []})
    u' a:: b\n{{{\n#!wiki comment\n}}}\n b::\n'

    Metas should not have ':: ' as it could cause problems with dl markup
    >>> replace_metas(request, 
    ...               u' test:: 1\n test:: 2', 
    ...               {}, 
    ...               {u"koo:: ": [u"a"]})
    u' test:: 1\n test:: 2\n koo:: a\n'

    Tests for different kinds of line feeds. Metas should not have \r
    or \n as it would cause problems. This is contrary to general
    MoinMoin logic to minimise user confusion.
    >>> replace_metas(request, 
    ...               u' a:: text\n',
    ...               {u'a': [u'text']},
    ...               {u'a': [u'text\r\n\r\nmore text']})
    u' a:: text  more text\n'

    >>> replace_metas(request, 
    ...               u' a:: text\n',
    ...               {u'a': [u'text']},
    ...               {u'a': [u'text\r\rmore text']})
    u' a:: textmore text\n'

    >>> replace_metas(request, 
    ...               u' a:: text\n',
    ...               {u'a': [u'text']},
    ...               {u'a': [u'text\n\nmore text']})
    u' a:: text  more text\n'

    # Just in case - regression of spaces at the end of metas
    >>> replace_metas(request, 
    ...               u'kk\n a:: Foo \n<<MetaTable>>',
    ...               {u'a': [u'Foo']},
    ...               {u'a': [u'Foo ', u'']})
    u'kk\n a:: Foo\n<<MetaTable>>\n'

    # Case759 regressions

    >>> replace_metas(request, 
    ...               u' key:: {{{ weohweovd\nwevohwevoih}}}\n gwikilabel:: Foo Bar \n',
    ...               {u'gwikilabel': [u'Foo Bar'], u'key': [u'{{{ weohweovd']},
    ...               {u'gwikilabel': [u'Foo Bar', u''], u'key': [u'{{{ weohwe', u'']})
    u' key:: {{{ weohwe\nwevohwevoih}}}\n gwikilabel:: Foo Bar\n'

    >>> replace_metas(request, 
    ...               u' key:: {{{ \nweohweovd\nwevohwevoih}}}\n gwikilabel:: Foo Bar \n',
    ...               {u'gwikilabel': [u'Foo Bar'], u'key': [u'{{{']},
    ...               {u'gwikilabel': [u'Foo Bar', u''], u'key': [u'{{{ weohwe', u'']})
    u' key:: {{{ weohwe\nweohweovd\nwevohwevoih}}}\n gwikilabel:: Foo Bar\n'

    >>> replace_metas(request, 
    ...               u' key:: {{{#!wiki \nweohweovd\nwevohwevoih}}}\n gwikilabel:: Foo Bar \n',
    ...               {u'gwikilabel': [u'Foo Bar'], u'key': [u'{{{#!wiki']},
    ...               {u'gwikilabel': [u'Foo Bar', u''], u'key': [u'{{{#!wiki weohwe', u'']})
    u' key:: {{{#!wiki weohwe\nweohweovd\nwevohwevoih}}}\n gwikilabel:: Foo Bar\n'

    >>> replace_metas(request, 
    ...               u' key:: {{{#!wiki weohweovd\nwevohwevoih}}}\n gwikilabel:: Foo Bar \n',
    ...               {u'gwikilabel': [u'Foo Bar'], u'key': [u'{{{#!wiki weohweovd']},
    ...               {u'gwikilabel': [u'Foo Bar', u''], u'key': [u'{{{#!wiki weohwe', u'']})
    u' key:: {{{#!wiki weohwe\nwevohwevoih}}}\n gwikilabel:: Foo Bar\n'

    # Case 676, new behaviour
    >>> replace_metas(request, 
    ...               u' gwikicategory:: CategoryOne CategoryTwo',
    ...               {u'gwikicategory': [u'CategoryOne', u'CategoryTwo']},
    ...               {u'gwikicategory': [u'CategoryOnes', u'CategoryTwo', u'', u'']})
    u'----\nCategoryOnes CategoryTwo\n'

    # Empty key behaviour
    >>> replace_metas(request, 
    ...               u' ::\n',
    ...               {},
    ...               {u'': [u'blaa', u'blöö', '']})
    u' ::\n'
    >>> replace_metas(request, 
    ...               u' :: \n :: blaa\n :: bl\xc3\xb6\xc3\xb6\n',
    ...               {},
    ...               {u'': [u'blaa', u'blöö', u'blyy', '']})
    u' :: \n :: blaa\n :: bl\xc3\xb6\xc3\xb6\n'

    """

    text = text.rstrip()
    # Annoying corner case with dl:s
    if text.endswith('::'):
        text = text + " \n"

    # Work around the metas whose values are preformatted fields (of
    # form {{{...}}})
    text, keys_to_markers, markers_to_keys = remove_preformatted(text)

    replaced_metas = dict()
    for key, values in oldmeta.iteritems():
        replaced_values = list()
        for value in values:
            replaced_values.append(keys_to_markers.get(value, value))
        replaced_metas[key] = replaced_values
    oldmeta = replaced_metas

    # Make clustering replaced and added values work
    # Example: Case739, where 
    # oldmeta['a'] = ['k'] and 
    # newmeta['a'] = ['', 'b']
    # need to revert the newmeta so that the value is replaced,
    # instead of first the value k getting removed and then the
    # value b cannot cluster as the key is there no more
    new_metas = dict()
    for key, values in newmeta.iteritems():
        # Keys should not be empty
        if not key:
            continue
        # Keys should not end in ':: ' as this markup is reserved
        key = key.rstrip(':: ').strip()

        if len(newmeta.get(key, [])) > len(oldmeta.get(key, [])):
            if values[0] == '':
                values.reverse()

        newvalues = list()
        for value in values:
            # Convert \r and \n to safe values, 
            # strip leading and trailing spaces
            value = value.replace("\r\n", " ")
            value = value.replace("\n", " ")
            value = value.replace("\r", "").strip()
            newvalues.append(value)

        new_metas[key] = newvalues
    newmeta = new_metas

    # Replace the values we can
    def dl_subfun(mo):
        alltext, key, val = mo.groups()

        key = key.strip()
        val = val.strip()

        # Categories handled separately (see below)
        if key == CATEGORY_KEY:
            return ""

        # Don't touch unmodified keys
        if key not in oldmeta:
            return alltext

        # Don't touch placeholders
        if not val:
            return ""

        # Don't touch unmodified values
        try:
            index = oldmeta[key].index(val)
        except ValueError:
            return alltext
        
        newval = newmeta[key][index]

        del oldmeta[key][index]
        del newmeta[key][index]
        
        if not newval:
            return ""

        retval = " %s:: %s\n" % (key, newval)
        if alltext.startswith('\n'):
            retval = '\n' + retval

        return retval

    text = DL_RE.sub(dl_subfun, text)

    # Handle the magic duality between normal categories (CategoryBah)
    # and meta style categories. Categories can be written on pages as
    # gwikicategory:: CategoryBlaa, and this should be supported as
    # long as the category values are valid. Categories should always
    # be written on pages as Moin-style, as a space-separated list on
    # the last line of the page
    oldcategories = oldmeta.get(CATEGORY_KEY, list())
    newcategories = newmeta.get(CATEGORY_KEY, list())

    added = filter_categories(request, newcategories)
    discarded = filter_categories(request, oldcategories)

    for index, value in reversed(list(enumerate(newcategories))):
        # Strip empty categories left by metaedit et al
        if not value.strip():
            del newcategories[index]

        if value not in added:
            continue

        if index < len(oldcategories):
            del oldcategories[index]
        del newcategories[index]

    if discarded:
        text = edit_categories(request, text, "del", discarded)
    if added:
        text = edit_categories(request, text, "add", added)

    # Fill in the prototypes
    def dl_fillfun(mo):
        alltext, key = mo.groups()
        key = key.strip()

        if key not in newmeta or not newmeta[key]:
            return alltext

        newval = newmeta[key].pop(0).replace("\n", " ").strip()

        return " %s:: %s\n" % (key, newval)
    text = DL_PROTO_RE.sub(dl_fillfun, text)

    # Add clustered values
    def dl_clusterfun(mo):
        alltext, key, val = mo.groups()

        key = key.strip()
        if key not in newmeta:
            return alltext

        for value in newmeta[key]:
            value = value.replace("\n", " ").strip()
            if value:
                alltext = " %s:: %s\n" % (key, value) + alltext

        newmeta[key] = list()
        return alltext
    text = DL_RE.sub(dl_clusterfun, text)

    # Add values we couldn't cluster
    for key, values in newmeta.iteritems():
        # Categories handled separately (see above)
        if key == CATEGORY_KEY:
            continue

        for value in values:
            # Empty values again supplied by metaedit and metaformedit
            if not value.strip():
                continue

            inclusion = " %s:: %s" % (key, value)
            text = add_meta_regex(request, inclusion, value, text)

    # Metas have been set, insert preformatted areas back
    for key in markers_to_keys:
        text = text.replace(key, markers_to_keys[key])

    # Add enter to the end of the line, as it was removed in the
    # beginning of this function, not doing so causes extra edits.
    return text.rstrip() + '\n'
