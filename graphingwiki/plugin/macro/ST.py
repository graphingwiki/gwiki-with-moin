# -*- coding: utf-8 -*-"
"""
    ST macro plugin to MoinMoin
     - draws a proper Finnish legistlation security stamp

    @copyright: 2009, 2011 by Juhani Eronen <exec@iki.fi>
    @license: MIT <http://www.opensource.org/licenses/mit-license.php>
"""
from MoinMoin.action import cache

from graphingwiki import cairo, have_cairo, cairo_surface_to_png
from graphingwiki.util import cache_key, cache_exists

LEVELS = {'2': 'SALAINEN',
          '3': 'LUOTTAMUKSELLINEN',
          '4': 'KÄYTTÖ RAJOITETTU'}

LEVELSROMAN = {'4': 'IV', '3': 'III', '2': 'II'}

LAW = u"JulkL (621/1999) 24.1 \xa7:n {0} k"

if have_cairo():
    CAIRO_BOLD = ("sans-serif", cairo.FONT_SLANT_NORMAL,
                                cairo.FONT_WEIGHT_BOLD)
    CAIRO_NORMAL = ("sans-serif", cairo.FONT_SLANT_NORMAL,
                                  cairo.FONT_WEIGHT_NORMAL)


def plot_box(texts):
    # Make a context to calculate font sizes with
    # There must be a better way to do this, I just don't know it!
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 0, 0)

    ctx = cairo.Context(surface)
    ctx.select_font_face("sans-serif", cairo.FONT_SLANT_NORMAL,
                         cairo.FONT_WEIGHT_BOLD)
    ctx.set_font_size(15)

    max_text_len = 0
    for leveltxt, style in texts:
        # Calculate surface size so that texts will fit
        cur_len = ctx.text_extents(leveltxt)[4]
        if cur_len > max_text_len:
            max_text_len = cur_len + 16

    box_height = 26 * len(texts)
    if len(texts) == 1:
        box_height += 8

    # Longest text fits lenght of 268, nicer if markings are of
    # regular size if possible
    if max_text_len < 268:
        max_text_len = 268
    # Make the actual surface
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32,
                                 int(max_text_len), box_height)

    ctx = cairo.Context(surface)
    ctx.select_font_face(*CAIRO_BOLD)
    ctx.set_font_size(15)
    ctx.set_line_width(0.6)

    # Fill surface with white
    width, height = surface.get_width(), surface.get_height()

    ctx.set_source_rgb(1.0, 1.0, 1.0)
    ctx.rectangle(0, 0, width, height)
    ctx.fill()

    ctx.set_line_width(10)
    ctx.set_source_rgb(1.0, 0, 0)
    ctx.rectangle(0, 0, width, height)
    ctx.stroke()

    curpos = 5

    for text, style in texts:
        curpos = curpos + 18
        ctx.select_font_face(*style)
        text_len = ctx.text_extents(text)[4] + 4
        ctx.move_to(max_text_len/2-(text_len/2) + 2, curpos)
        ctx.show_text(text)

    return cairo_surface_to_png(surface)


def plot_tll(level='4', text='7', law=None):
    if level not in LEVELS:
        level = '4'
    if not law:
        law = LAW.format(text)

    texts = [(LEVELS[level], CAIRO_BOLD),
             ('Suojaustaso {0}'.format(LEVELSROMAN[level]), CAIRO_BOLD),
             (law, CAIRO_NORMAL)]

    return plot_box(texts)


def execute(macro, args):
    request = macro.request

    # Handle GET arguments
    level = '4'
    level_text = '7'

    if not args:
        args = ''

    arglist = [x.strip() for x in args.split(',') if x]

    if not have_cairo():
        return "Cairo not found."

    key = cache_key(request, (macro.name, arglist))

    if not cache_exists(request, key):
        law = None
        if len(arglist) == 1:
            level = args[0]
        elif len(arglist):
            level = args[0]
            if arglist[1].isdigit():
                level_text = ','.join(arglist[1:])
            else:
                level_text = ''
                law = ','.join(arglist[1:])

        data = plot_tll(level, level_text, law)
        cache.put(request, key, data, content_type='image/png')

    f = macro.formatter

    divfmt = {"class": "ST"}

    result = f.div(1, **divfmt)
    result += f.image(src=cache.url(request, key), alt=LAW.format(level_text))
    result += f.div(0)
    return result
