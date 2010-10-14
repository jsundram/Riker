#!/usr/bin/env python
"""
Created by Jason Sundram.

Like Picard (Musicbrainz tagger), only using ENMFP: 
http://blog.echonest.com/post/545323349/the-echo-nest-musical-fingerprint-enmfp

You need to have installed the ENMFP before this will work:
please email enmfp@echonest.com for access to the binaries.
(Response is usually very fast).
"""

import os, sys

from pyechonest import song
from pyechonest.util import EchoNestAPIError

from metadata import Metadata

usage = """
The command line argument, if specified, is a file to update, or a folder full of .mp3 files, each of which will be updated.
If none is specified, the current directory is used.

The default behavior is to update the ID3 tags if they exist, but never to overwrite existing data.
"""

def fullpath(folder, filename):
    """Want canonical path to this file"""
    return os.path.realpath(os.path.join(folder, filename))
    
def main(folder):
    if folder.endswith('.mp3'):
        files = [folder]
    else:
        # iterate over all .mp3 files in this directory, and identify them.
        files = [fullpath(folder, f) for f in os.listdir(folder) if f.endswith('.mp3')]
        
    updated = 0
    for path in files:
        print os.path.basename(path)
        songs = None
        try:
            songs = song.identify(path, buckets=['audio_summary'])
        except EchoNestAPIError, e:
            print "API Error: %s" % e
            continue
            
        s = songs and songs.pop()
        if not s:
            print "Couldn't resolve %s" % path
            continue
        
        m = Metadata(s)
        m.write_id3(path, create_only=False, replace=False)
        updated += 1
    
    print "Updated %d / %d files" % (updated, len(files))
    
if __name__ == '__main__':
    try:
        d = sys.argv[1]
    except Exception:
        d = os.getcwd()
    sys.exit(main(d))