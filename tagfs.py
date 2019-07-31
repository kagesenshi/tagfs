#!/usr/bin/env python

#    Copyright (C) 2006  Andrew Straw  <strawman@astraw.com>
#
#    This program can be distributed under the terms of the GNU LGPL.
#    See the file COPYING.
#

import os, stat, errno
import fuse
from fuse import FUSE, Operations, LoggingMixIn, FuseOSError
import gi
from gi.repository import Tracker
from urllib.parse import urlparse, unquote, quote
import subprocess
from errno import *
from time import time

CACHE = {}
DEBUG = False

class TrackerWrapper(object):

    def __init__(self):
        self.conn = Tracker.SparqlConnection.get (None)

    def tags(self):
        cursor = self.conn.query ("SELECT ?labels  WHERE { ?tags a nao:Tag; nao:prefLabel ?labels; }", None)
        while (cursor.next(None)):
            d = cursor.get_string(0)[0]
            yield(d)

    def files(self, tag):
        if CACHE.get('files', None):
            if CACHE['files'].get(tag, None):
                if int(time()) < CACHE['files'][tag]['ts'] + 5:
                    return CACHE['files'][tag]['data']

        files = []
        cursor = self.conn.query ('''
                SELECT nfo:fileName(?f) nie:url(?f) WHERE {
                    ?f a nfo:FileDataObject ; 
                        nao:hasTag [ nao:prefLabel "%s" ] }''' % tag, None)

        while (cursor.next(None)):
            d = cursor.get_string(0)[0]
            u = cursor.get_string(1)[0]
            files.append(u)

        CACHE.setdefault('files', {})
        CACHE['files'].setdefault(tag, {})
        CACHE['files'][tag]['ts'] = int(time())
        CACHE['files'][tag]['data'] = files
        return files


    def get_file(self, tag, name):
        for f in self.files(tag):
            if os.path.basename(f) == name:
                return f

    def create_tag(self, tag):
        if tag in list(self.tags()):
            return 
        cursor = self.conn.update('''
            INSERT {  _:tag a nao:Tag ;
                      nao:prefLabel '%(tag)s' .
            }''' % {'tag': tag}, 0, None)

    def tag(self, tag, path):
        cursor = self.conn.update('''
            INSERT {
              ?unknown nao:hasTag ?id
            } WHERE {
              ?unknown nie:isStoredAs ?as .
              ?as nie:url 'file://%(path)s' .
              ?id nao:prefLabel '%(tag)s'
            }''' % {'tag': tag, 'path': path}, 0, None)

    def untag(self, tag, path):
        subprocess.Popen(['tracker','tag','-d', tag, path]).wait()


    def delete_tag(self, tag):
        subprocess.Popen(['tracker','tag','-d', tag]).wait()


class TagFS(LoggingMixIn, Operations):

    def __init__(self):
        self.tracker = TrackerWrapper()

    def getattr(self, path, fh=None):
        st = {
            'st_mode' : 0,
            'st_ino' : 0,
            'st_dev' : 0,
            'st_nlink' : 0,
            'st_uid' : 0,
            'st_gid' : 0,
            'st_size' : 0,
            'st_atime' : 0,
            'st_mtime' : 0,
            'st_ctime' : 0,
        }

        tags = list(self.tracker.tags())

        tag = None
        name = None
        if path.count('/') == 1:
            tag = path[1:]
        elif path.count('/') == 2:
            tag, name = path[1:].split('/')

        if path == '/' or (path.count('/') == 1 and tag in tags):
            st['st_mode'] = stat.S_IFDIR | 0o755
            st['st_nlink'] = 2
        elif path.count('/') == 2 and self.tracker.get_file(tag, name):
            st['st_mode'] = 41471
            st['st_nlink'] = 1
            st['st_size'] = 0
        else:
            raise FuseOSError(ENOENT)
        return st

    def readdir(self, path, offset):
        now = time()
        for i in ['.','..']:
            yield i
        if path == '/':
            for t in self.tracker.tags():
                yield t
        else:
            tag = path[1:]
            files = self.tracker.files(tag)
            for u in files:
                yield os.path.basename(u)



    def readlink(self, path):
        tag, name = path[1:].split('/')
        url = self.tracker.get_file(tag, name)
        up = urlparse(url)
        return unquote(up.path)

    def rmdir(self, path):
        if path.count('/') == 1:
            tag = path[1:]
            self.tracker.delete_tag(tag)
        else:
            raise FuseOSError(EROFS)

    def mkdir(self, path, mode):
        if path.count('/') == 1:
            self.tracker.create_tag(path[1:])
        else:
            raise FuseOSError(EROFS)

    def symlink(self, target, source):
        if not target.startswith('/'):
            raise FuseOSError(EOPNOTSUPP)
        if target.count('/') == 1:
            raise FuseOSError(EOPNOTSUPP)
        tag, dest = target[1:].split('/')
        self.tracker.tag(tag, source)

        CACHE['files'][tag] = {} # flush

    def unlink(self, path):
        if path.count('/') == 1:
            raise FuseOSError(EOPNOTSUPP)
        tag, url = path[1:].split('/')
        url = unquote(urlparse(url).path)
        self.tracker.untag(tag, url)

        CACHE['files'][tag] = {} # flush

    def statfs(self, path):
        return dict(
            f_bsize=512, f_blocks=4096, f_bavail=2048,
            f_namemax=4096
            )

def main():

    import argparse
    import logging
    parser = argparse.ArgumentParser()
    parser.add_argument('mount')
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG)

    opts = {
        'foreground': True,
        'nothreads': True,
        'allow_other': False
    }

    if not DEBUG:
        opts['foreground'] = False
        opts['nothreads'] = False

    fuse = FUSE(TagFS(), args.mount, **opts)

if __name__ == '__main__':
    main()
