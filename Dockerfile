FROM ubuntu:14.04
MAINTAINER exec@iki.fi

# Dependencies, will minimise later
RUN apt-get update && apt-get install -y \
 software-properties-common
RUN add-apt-repository ppa:igraph/ppa
RUN apt-get update && apt-get install -y \
 python-igraph \
 libapache2-mod-wsgi \
 apache2 \
 apache2-mpm-worker \
 ssl-cert \
 libgv-python \
 graphviz \
 emacs \
 && rm -rf /var/lib/apt/lists/*


# Setup directory structure
ENV SRC=/usr/local/src/gwiki-with-moin COLLABS=/srv/wikis/collab
RUN umask 022 && mkdir -p $COLLABS $SRC /etc/local/collab/ 

WORKDIR $COLLABS/
RUN mkdir -p archive cache config docbook htdocs log underlay user wikis run
COPY . $SRC/

WORKDIR $SRC/
RUN python setup-MoinMoin.py install && python setup-collabbackend.py install \
 && python setup.py install


# Apache setup, basic service setup
RUN a2enmod ssl && a2enmod rewrite

RUN mkdir -p /srv/www/log/https/ /srv/www/https/ \
 && chown www-data:www-data /srv/www/log/https/ /srv/www/https/

RUN cp config/apache2.4/collab.conf /etc/apache2/conf-enabled/ \
 && cp config/apache2.4/000-default.conf /etc/apache2/sites-available/ \
 && cp config/apache2.4/ports.conf /etc/apache2/ \
 && a2ensite 000-default.conf

RUN useradd -u 812 -s /sbin/nologin -c 'Service Collab' collab \
 && usermod -a -G collab www-data

RUN cp config/collab.ini /etc/local/collab/ \
 && cp config/collabfarm.py config/intermap.txt config/logging.conf \
 "$COLLABS/config/"


# Htdocs, underlays, ...
WORKDIR /srv/wikis/
RUN touch collab/log/moinmoin.log && chmod 660 collab/log/moinmoin.log

RUN ln -sf $COLLABS/htdocs/ /srv/www/https/collab \
 && ln -s /usr/local/share/moin/htdocs/ /srv/www/https/moin_static \
 && cp -r $SRC/MoinMoin/web/static/htdocs/* /usr/local/share/moin/htdocs/

RUN tar -C $COLLABS/ -xf /usr/local/share/moin/underlay.tar

RUN chgrp -R collab /usr/local/share/moin/ \
 && chown -R collab:collab $COLLABS/ && chmod -R 2770 $COLLABS/


# Base collab setup
RUN su - collab -s /bin/bash -c "collab-create collab collab" \
 && su - collab -s /bin/bash -c "collab-account-create -f -r collab" \
 && su - collab -s /bin/bash -c "collab-htaccess" \
 && cp $SRC/config/apache2.4/htaccess $COLLABS/htdocs/.htaccess

RUN PYTHONPATH=$COLLABS/wikis/collab/config/ \
 python -m MoinMoin.packages i $SRC/packages/CollabBase.zip

RUN su - collab -s /bin/bash -c "gwiki-rehash $COLLABS/wikis/collab"


# Finishing touches
EXPOSE 443
CMD ["/usr/sbin/apache2ctl","-DFOREGROUND"]
