# -*- coding: utf-8 -*-"
"""
    CL macro plugin to MoinMoin
     - Draws configurable classification markings

    @copyright: 2011 by Juhani Eronen <exec@iki.fi>
    @license: MIT <http://www.opensource.org/licenses/mit-license.php>
"""
from MoinMoin.action import cache

from graphingwiki import have_cairo
from graphingwiki.util import cache_key, cache_exists

if have_cairo():
    from ST import plot_box, CAIRO_BOLD
    DEFAULT = [('COMPANY CONFIDENTIAL', CAIRO_BOLD)]


def execute(macro, args):
    request = macro.request

    if not have_cairo():
        return "Cairo not found."

    if not args:
        key = DEFAULT
    elif not hasattr(request.cfg, 'gwiki_markings'):
        return "No gwiki_markings in configuration."
    else:
        try:
            val = request.cfg['gwiki_markings'][args]
            key = list()
            for line in val:
                if not isinstance(line, unicode):
                    return ("Marking misconfiguration " +
                            "(not a tuple of unicode strings)")
                key.append((line, CAIRO_BOLD))
        except KeyError:
            return "Marking not in gwiki_markings."

    level_text = ' '.join(x[0] for x in key)
    ckey = cache_key(request, (macro.name, key))

    if not cache_exists(request, ckey):
        data = plot_box(key)
        cache.put(request, ckey, data, content_type='image/png')

    f = macro.formatter

    divfmt = {"class": "CM"}

    result = f.div(1, **divfmt)
    result += f.image(src=cache.url(request, ckey), alt=level_text)
    result += f.div(0)
    return result
