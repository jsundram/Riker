import eyeD3
import os
import string
try:
    import simplejson as json
except ImportError:
    import json
import unicodedata
import urllib

from pyechonest import config
config.TRACE_API_CALLS = False
from pyechonest import song, artist
MUSIC_MATCH_API_KEY = os.getenv('MUSIC_MATCH_API_KEY') # mine

def normalize(s):
    return unicodedata.normalize('NFKD', unicode(s)).encode('ascii','ignore').strip()

class Metadata(object):
    def __init__(self, s):
        """s is a pyechonest.Song object"""
        # useful info
        self.artist, self.title, self.song_id, self.artist_id, self.bpm = normalize(s.artist_name), normalize(s.title), s.id, s.artist_id, int(s.audio_summary.tempo)
        
        # lyrics
        self.artist_musicbrainz_id, self.track_musicbrainz_id, self.lyrics = self.get_lyrics()
        
        # genre
        a = artist.Artist(s.artist_id)
        terms = [t.name for t in a.terms]
        self.genre = string.capwords(normalize(terms[0])) if terms else None
        
        # album art
        self.album_art_url = self.get_album_art_url()
        
        # TODO: Is there any way to get album/release?
    
    def get_lyrics(self):
        """Uses the MusixMatch API to return musicbrainz ids for artist and title, along with lyrics (unicode string)"""
        track_mbid, artist_mbid, lyrics = None, None, None
        
        artist, title = self.artist, self.title
        base_url = 'http://api.musixmatch.com/ws/1.0/'
        
        def get_ids():
            keys = ['lyrics_id', 'track_mbid', 'artist_mbid']
            params = {'artist': artist, 'q_track': title, 'apikey': MUSIC_MATCH_API_KEY, 'format': 'json', 'page_size': 1, 'f_has_lyrics': 1}
            track_search_url = '?'.join([base_url + 'track.search', urllib.urlencode(params)])
            
            try:
                response = json.loads(urllib.urlopen(track_search_url).read())
                track_info = response['message']['body']['track_list'][0]['track']
            except Exception, e:
                print "\t\tCouldn't find lyrics for track %s by %s" % (title, artist)
            else:
                return map(track_info.get, keys)
            return (None, None, None)
        
        def _get_lyrics(lyrics_id):
            if not lyrics_id: return None
            
            params = {'lyrics_id': lyrics_id, 'format':'json', 'apikey': MUSIC_MATCH_API_KEY}
            lyrics_get_url = '?'.join([base_url + 'lyrics.get', urllib.urlencode(params)])
            try:
                response = json.loads(urllib.urlopen(lyrics_get_url).read())
                return response['message']['body']['lyrics_list'][0]['lyrics']['lyrics_body']
            except Exception, e:
                print "\t\tException getting lyrics: %s" % str(e)
        
        print "\tLooking for lyrics for %s: %s" % (artist, title)
        lid, amb, tmb = get_ids()
        return str(amb), str(tmb), _get_lyrics(lid)
    
    def get_album_art_url(self):
        """Searches 7digital for the given song/track, and goes for the song if it can't match the track"""
        song_id = self.song_id
        
        songs = []
        if song_id:
            print "\tSearching for album art for %s" % song_id
            songs = song.profile(song_id, buckets=['tracks', 'id:7digital'], limit=True)
        # if we couldn't get songs from 7digital with this songID go ahead and try a search.
        if not songs:
            print "\tSearching for album art for %s: %s" % (self.artist, self.title)
            songs = song.search(artist=self.artist, title=self.title, buckets=['tracks', 'id:7digital'], limit=True)
        
        for s in songs:
            tracks = s.get_tracks('7digital')
            for t in tracks:
                if 'release_image' in t:      # TODO: should we check metadata match?
                    return t['release_image'] # e.g. u'http://cdn.7static.com/static/img/sleeveart/00/005/658/0000565851_200.jpg'
    
    # replace, update, create_only
    def write_id3(self, mp3_path, create_only=False, replace=False):
        """ create_only: only write data if there is not an existing id3 tag.
            replace: only write data if there is no data in the field (e.g.)
        """
        filename = os.path.basename(mp3_path)
        tag = eyeD3.Tag()
        def get_aa(url):
            if url:
                tmp = 'aa.jpg' # TODO: could be nice and use tempfile
                if os.path.exists(tmp): # Necessary?
                    os.remove(tmp)
                try:
                    urllib.urlretrieve(url, tmp)
                    return tmp
                except Exception, e:
                    print str(e)
            return None
        
        has_tags = tag.link(mp3_path)
        # TODO: reorganize the code so that we don't do the lookups in init if create_only and has_tags
        if not (create_only and has_tags):
            print "\tUpdating file %s" % filename
            try:
                tag.header.setVersion(eyeD3.ID3_V2_3)
                if replace or not tag.getTitle():
                    tag.setTitle(self.title)
                if replace or not tag.getartist():
                    tag.setArtist(self.artist)
                if replace or not tag.getBPM():
                    tag.setBPM(self.bpm)
                if replace or not tag.getGenre():
                    tag.setGenre(self.genre)
                if replace or not tag.getComment():
                    ids = [self.song_id, self.artist_id]
                    tag.addComment(', '.join(map(str, ids)), desc='EN IDs')
                
                # Begin Fancy shit.
                if self.track_musicbrainz_id:
                    tag.addUniqueFileID('http://musicbrainz.org', str(self.track_musicbrainz_id))
                if self.artist_musicbrainz_id:
                    tag.addUserTextFrame('MusicBrainz Artist Id', str(self.artist_musicbrainz_id))
                
                has_cover = eyeD3.ImageFrame.FRONT_COVER in [i.pictureType for i in tag.getImages()]
                if replace or not has_cover:
                    aa = get_aa(self.album_art_url)
                    if aa:
                        tag.addImage(eyeD3.ImageFrame.FRONT_COVER, aa, desc='image from 7digital')
                if replace or not tag.getLyrics():
                    tag.addLyrics(self.lyrics, desc='from musixmatch.com')
            except Exception, e:
                print "\tException updating metadata: %s" % str(e)
                raise # TODO pass?
            finally:
                try:
                    tag.update()
                except Exception, e:
                    print "\tUnable to save tag: %s" % str(e)
