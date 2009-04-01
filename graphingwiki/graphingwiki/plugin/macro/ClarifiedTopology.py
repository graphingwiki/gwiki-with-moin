# -*- coding: utf-8 -*-"
"""
    ClarifiedTopology macro plugin to MoinMoin/Graphingwiki
     - Shows the Topology information generated by Clarified
       Analyser as an image

    @copyright: 2008 by Juhani Eronen <exec@iki.fi>
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
import math

from MoinMoin.action import cache
from MoinMoin.action import AttachFile
from MoinMoin.macro.Include import _sysmsg

from graphingwiki.plugin.action.metasparkline import write_surface
from graphingwiki.editing import metatable_parseargs, get_metas
from graphingwiki.util import form_escape, make_tooltip

cairo_found = True
try:
    import cairo
except ImportError:
    cairo_found = False
    pass

Dependencies = ['metadata']

def execute(macro, args):
    formatter = macro.formatter
    macro.request.page.formatter = formatter
    request = macro.request
    _ = request.getText

    if not args:
        args = request.page.page_name

    key = "MetaMap(%s)" % (args)

    topology = args

    # Get all containers
    args = 'CategoryContainer, %s=/.+/' % (args)

    #request.write(args)

    # Note, metatable_parseargs deals with permissions
    pagelist, metakeys, styles = metatable_parseargs(request, args,
                                                     get_all_keys=True)
    
    if not pagelist:
        return _sysmsg % ('error', "%s: %s" % 
                          (_("No such topology or empty topology"), 
                           form_escape(topology)))

    coords = dict()
    images = dict()
    aliases = dict()
    areas = dict()

    allcoords = list()
    for page in pagelist:
        data = get_metas(request, page, 
                         [topology, 'gwikishapefile', 'tia-name'],
                         display=True, checkAccess=False)

        crds = [x.split(',') for x in data.get(topology, list)]

        if not crds:
            continue
        crds = [x.strip() for x in crds[0]]
        if not len(crds) == 2:
            continue

        try:
            start_x, start_y = int(crds[0]), int(crds[1])
        except ValueError:
            continue

        coords[page] = start_x, start_y
        allcoords.append((start_x, start_y))

        img = data.get('gwikishapefile', list())

        if img:
            img = img[0].split('/')[-1]
            imgname = AttachFile.getFilename(request, page, img)
            try:
                images[page] = cairo.ImageSurface.create_from_png(imgname)
                end_x = start_x + images[page].get_width()
                end_y = start_y + images[page].get_height()
            except cairo.Error:
                pass

        # If there was no image or a problem with loading the image
        if not page in images:
            # Lack of image -> black 10x10 rectangle is drawn
            end_x, end_y = start_x + 10, end_x + 10

        allcoords.append((end_x, end_y))

        alias = data.get('tia-name', list())
        if alias:
            aliases[page] = alias[0]

    max_x = max([x[0] for x in allcoords])
    min_x = min([x[0] for x in allcoords])
    max_y = max([x[1] for x in allcoords])
    min_y = min([x[1] for x in allcoords])

    # Make room for text under pictures
    surface_y = max_y - min_y + 25
    surface_x = max_x - min_x

    # Setup Cairo
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32,
                                 surface_x, surface_y)
    # request.write(repr([surface_x, surface_y]))
    ctx = cairo.Context(surface)
    ctx.select_font_face("Times-Roman", cairo.FONT_SLANT_NORMAL,
                         cairo.FONT_WEIGHT_BOLD)
    ctx.set_font_size(12)

    ctx.set_source_rgb(1.0, 1.0, 1.0)
    ctx.rectangle(0, 0, surface_x, surface_y)
    ctx.fill()

    for page in pagelist:
        if not coords.has_key(page):
            continue

        x, y = coords[page]
#         request.write('<br>' + repr(get_metas(request, page, ['tia-name'])) + '<br>')
#         request.write(repr(coords[page]) + '<br>')
#         request.write(str(x-min_x) + '<br>')
#         request.write(str(y-min_y) + '<br>')

        start_x = x-min_x
        start_y = y-min_y

        w, h = 10, 10
        if not images.has_key(page):
            ctx.set_source_rgb(0, 0, 0)
        else:
            h = images[page].get_height()
            w = images[page].get_width()
            ctx.set_source_surface(images[page], start_x, start_y)
        
        ctx.rectangle(start_x, start_y, w, h)

        pagedata = request.graphdata.getpage(page)
        text = make_tooltip(request, pagedata)

        areas["%s,%s,%s,%s" % (start_x, start_y, start_x + w, start_y + h)] = \
            [page, text, 'rect']

        ctx.fill()

        if page in aliases:
            ctx.set_source_rgb(0, 0, 0)
            ctx.move_to(start_x, start_y + h + 10)
            ctx.show_text(aliases[page])

    s2 = surface
# Proto for scaling and rotating code
#     scale = 1
#     rotate = 1

#     if scale:
#         # For scaling
#         new_surface_y = 1000.0
#         new_surface_x = surface_x / (surface_y/new_surface_y)
#     else:
#         new_surface_y = surface_y
#         new_surface_x = surface_x

#     if rotate:
#         temp = new_surface_x
#         new_surface_x = new_surface_y
#         new_surface_y = temp
#         temp = surface_x
#         surface_x = surface_y
#         surface_y = temp
#         transl = -surface_x

#     s2 = cairo.ImageSurface(cairo.FORMAT_ARGB32,
#                                  new_surface_x, new_surface_y)

#     ctx = cairo.Context(s2)

#     if rotate:
#         ctx.rotate(90.0*math.pi/180.0)

#     if scale:
#         ctx.scale(new_surface_x/surface_x, new_surface_y/surface_y)

#     if rotate:
#         ctx.translate(0, -surface_x)
        
#     ctx.set_source_surface(surface, 0, 0)
#     ctx.paint()

    data = write_surface(surface)
    cache.put(request, key, data, content_type='image/png')

    map_text = 'usemap="#%s" ' % (id(ctx))

    div = u'<div class="ClarifiedTopology">\n' + \
        u'<img %ssrc="%s" alt="%s">\n</div>\n' % \
        (map_text, cache.url(request, key), _('topology'))

    map = u'<map id="%s" name="%s">\n' % (id(ctx), id(ctx))
    for coords in areas:
        name, text, shape = areas[coords]
        pagelink = request.getScriptname() + u'/' + name

        tooltip = "%s\n%s" % (name, text)

        map += u'<area href="%s" shape="%s" coords="%s" title="%s">\n' % \
            (form_escape(pagelink), shape, coords, tooltip)
    map += u'</map>\n'
    
    return div + map
