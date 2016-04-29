# -*- coding: utf-8 -*-

from MoinMoin.theme import modernized as basetheme
from opencollab import Theme as ThemeParent

NAME = "ficora"


class Theme(ThemeParent):
    name = NAME
    css_files = ['screen']

    def footer_string(self):
        if hasattr(self.cfg, 'footer_string'):
            footer_string = self.cfg.footer_string
        else:
            footer_string = \
                u'  <p class="footertext">Viestintävirasto<br>' + \
                u'Kyberturvallisuuskeskus<br>PL 313<br>00181 Helsinki'+ \
                u'<br>Tel. +358 (0)295 390 230</p>'

        return footer_string

    def logo(self):
        mylogo = basetheme.Theme.logo(self)
        if not mylogo:
            mylogo = u'<a href="' + \
                self.request.script_root + '/' + self.request.cfg.page_front_page + \
                '"><img src="' + self.cfg.url_prefix_static + \
                '/ficora/img2/kyberturvallisuus_neg_rgb.png" alt="CERT-FI"></a>'
        return mylogo
