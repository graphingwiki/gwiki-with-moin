# -*- coding: utf-8 -*-
"""
    CollabExpiry macro plugin to MoinMoin
     - Show notice or warning when collab is expiring

    @copyright: 2016 Ossi Salmi
    @license: MIT <http://www.opensource.org/licenses/mit-license.php>

"""
from datetime import datetime, timedelta

from graphingwiki.editing import get_metas

Dependencies = ['metadata']


def format_msg(f, message, warning=False):
    if warning:
        strongfmt = {'class': 'warning'}
    else:
        strongfmt = {}

    msg = f.div(1)
    msg += f.strong(1, **strongfmt)
    msg += f.text(message)
    msg += f.strong(0)
    msg += f.div(0)
    return msg


def execute(self, args):
    request = self.request
    _ = request.getText
    f = self.formatter

    page = "CollabFacts"
    key = "expires"
    delta = None
    warning = False

    if args:
        try:
            delta = timedelta(days=int(args))
        except (OverflowError, ValueError):
            return format_msg(f, _("Argument must be an integer."), True)

    vals = get_metas(request, page, [key])
    if not vals[key]:
        return ""
    val = vals[key][0]

    try:
        expires = datetime.strptime(val, "%Y-%m-%d")
    except ValueError:
        return format_msg(f, _("Invalid expires meta in CollabFacts."), True)

    if delta:
        if expires - delta > datetime.now():
            return ""
        warning = True

    msg = _("This collab will expire on %s.") % val

    return format_msg(f, msg, warning)
