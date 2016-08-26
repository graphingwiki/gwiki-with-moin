#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
"""
    MoinMoin installer

    @copyright: 2001-2005 by Jürgen Hermann <jh@web.de>,
                2006-2014 by MoinMoin:ThomasWaldmann
    @license: GNU GPL, see COPYING for details.
"""

import os, sys, glob

from setuptools import setup, find_packages

from MoinMoin.version import release, revision


#############################################################################
### Helpers
#############################################################################

def isbad(name):
    """ Whether name should not be installed """
    return (name.startswith('.') or
            name.startswith('#') or
            name.endswith('.pickle') or
            name == 'CVS')

def isgood(name):
    """ Whether name should be installed """
    return not isbad(name)

def makeDataFiles(prefix, dir):
    """ Create distutils data_files structure from dir

    distutil will copy all file rooted under dir into prefix, excluding
    dir itself, just like 'ditto src dst' works, and unlike 'cp -r src
    dst, which copy src into dst'.

    Typical usage:
        # install the contents of 'wiki' under sys.prefix+'share/moin'
        data_files = makeDataFiles('share/moin', 'wiki')

    For this directory structure:
        root
            file1
            file2
            dir
                file
                subdir
                    file

    makeDataFiles('prefix', 'root')  will create this distutil data_files structure:
        [('prefix', ['file1', 'file2']),
         ('prefix/dir', ['file']),
         ('prefix/dir/subdir', ['file'])]

    """
    # Strip 'dir/' from of path before joining with prefix
    dir = dir.rstrip('/')
    strip = len(dir) + 1
    found = []
    os.path.walk(dir, visit, (prefix, strip, found))
    return found

def visit((prefix, strip, found), dirname, names):
    """ Visit directory, create distutil tuple

    Add distutil tuple for each directory using this format:
        (destination, [dirname/file1, dirname/file2, ...])

    distutil will copy later file1, file2, ... info destination.
    """
    files = []
    # Iterate over a copy of names, modify names
    for name in names[:]:
        path = os.path.join(dirname, name)
        # Ignore directories -  we will visit later
        if os.path.isdir(path):
            # Remove directories we don't want to visit later
            if isbad(name):
                names.remove(name)
            continue
        elif isgood(name):
            files.append(path)
    destination = os.path.join(prefix, dirname[strip:])
    found.append((destination, files))

def make_filelist(dir, strip_prefix=''):
    """ package_data is pretty stupid: if the globs that can be given there
        match a directory, then setup.py install will fall over that later,
        because it expects only files.
        Use make_filelist(dir, strip) to create a list of all FILES below dir,
        stripping off the strip_prefix at the left side.
    """
    found = []
    def _visit((found, strip), dirname, names):
        files = []
        for name in names:
            path = os.path.join(dirname, name)
            if os.path.isfile(path):
                if path.startswith(strip):
                    path = path[len(strip):]
                files.append(path)
        found.extend(files)

    os.path.walk(dir, _visit, (found, strip_prefix))
    return found


#############################################################################
### Call setup()
#############################################################################

setup_args = {
    'name': "moin",
    'version': release,
    'description': "MoinMoin %s is an easy to use, full-featured and extensible wiki software package" % (release, ),
    'author': "Juergen Hermann et al.",
    'author_email': "moin-user@lists.sourceforge.net",
    # maintainer(_email) not active because distutils/register can't handle author and maintainer at once
    'download_url': 'http://static.moinmo.in/files/moin-%s.tar.gz' % (release, ),
    'url': "http://moinmo.in/",
    'license': "GNU GPL",
    'long_description': """
    MoinMoin is an easy to use, full-featured and extensible wiki software
    package written in Python. It can fulfill a wide range of roles, such as
    a personal notes organizer deployed on a laptop or home web server,
    a company knowledge base deployed on an intranet, or an Internet server
    open to individuals sharing the same interests, goals or projects.""",
    'classifiers': """Development Status :: 5 - Production/Stable
Environment :: No Input/Output (Daemon)
Environment :: Web Environment
Intended Audience :: Developers
Intended Audience :: System Administrators
Intended Audience :: Education
Intended Audience :: Science/Research
Intended Audience :: End Users/Desktop
Intended Audience :: Information Technology
License :: OSI Approved :: GNU General Public License v2 or later (GPLv2+)
Operating System :: OS Independent
Operating System :: POSIX
Operating System :: POSIX :: BSD
Operating System :: POSIX :: Linux
Operating System :: Unix
Operating System :: MacOS :: MacOS X
Operating System :: Microsoft :: Windows
Programming Language :: Python
Programming Language :: Python :: 2
Programming Language :: Python :: 2.5
Programming Language :: Python :: 2.6
Programming Language :: Python :: 2.7
Topic :: Internet :: WWW/HTTP :: Dynamic Content
Topic :: Internet :: WWW/HTTP :: WSGI
Topic :: Internet :: WWW/HTTP :: WSGI :: Application
Topic :: Office/Business :: Groupware
Topic :: Text Processing :: Markup""".splitlines(),

    'packages': find_packages(exclude=["*._tests"]),

    'package_dir': {'MoinMoin.i18n': 'MoinMoin/i18n',
                    'MoinMoin.web.static': 'MoinMoin/web/static',
                   },
    'package_data': {'MoinMoin.i18n': ['README', 'Makefile', 'MoinMoin.pot', 'POTFILES.in',
                                       '*.po',
                                       'tools/*',
                                       'jabberbot/*',
                                      ],
                     'MoinMoin.web.static': make_filelist('MoinMoin/web/static/htdocs',
                                                          strip_prefix='MoinMoin/web/static/'),
                    },

    'entry_points': {
        'console_scripts': [
            'moin=MoinMoin.script.moin:run'
        ]
    },

    # This copies the contents of wiki dir under sys.prefix/share/moin
    # Do not put files that should not be installed in the wiki dir, or
    # clean the dir before you make the distribution tarball.
    'data_files': makeDataFiles('share/moin', 'wiki')
}


if __name__ == '__main__':
    setup(**setup_args)
