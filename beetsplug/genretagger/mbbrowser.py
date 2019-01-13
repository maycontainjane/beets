# -*- coding: utf-8 -*-
# This file is part of beets.
# Copyright 2016, Adrian Sampson.
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
# -*- coding: utf-8 -*-
# This file is part of beets.
# Copyright 2016, Adrian Sampson.
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
import six

import musicbrainzngs as mbn

from beets import plugins
import beets

from . import genrebrowser

class MusicBrainzBrowser(genrebrowser.GenreBrowser):
    """
    Takes in logger for debug messages
    """
    def __init__(self, log):
        self.log = log
        self.name = "musicbrainz"
        mbn.set_useragent('beets', beets.__version__, 'http://beets.io/')

        super(MusicBrainzBrowser, self).__init__()

    def fetch_album_genre(self, obj):
        """Return the album genre for this Item or Album.
        """
        # release groups give larger chance to get genre
        mbn_id = mbn.search_release_groups(obj.album, limit=1)["release-group-list"][0]["id"]
        tags = self._last_lookup(
            u'album', mbn.get_release_group_by_id, mbn_id, mbentity='release-group'
        )
        if tags == []:
            mbn_id = mbn.search_releases(obj.album, limit=1)["release-list"][0]["id"]
            tags = self._last_lookup(
                u'album', mbn.get_release_by_id, mbn_id, mbentity='release'
            )
            return tags
        # return ["tag", "tag", "tag"] from {"tag-list": {"count": 1, "name": "tag"}, } etc.}

    def fetch_album_artist_genre(self, obj):
        """Return the album artist genre for this Item or Album.
        """
        mbn_id = mbn.search_artists(obj.albumartist, limit=1)["artist-list"][0]["id"]
        return self._last_lookup(
            u'artist', mbn.get_artist_by_id, mbn_id
        )

    def fetch_artist_genre(self, item):
        """Returns the track artist genre for this Item.
        """
        mbn_id = mbn.search_artists(item.artist, limit=1)["artist-list"][0]["id"]
        return self._last_lookup(
            u'artist', mbn.get_artist_by_id, mbn_id
        )

    def fetch_track_genre(self, item):
        """Returns the track genre for this Item.
        """
        mbn_id = mbn.search_recordings(item.title, limit=1)["recording-list"][0]["id"]
        return self._last_lookup(
            u'track', mbn.get_track_by_id, mbn_id, mbentity='recording'
        )

    def _tags_for(self, tags, entity=None):
        """Core genre identification routine.

        Given an entity (album or track), return a list of
        tag names for that entity from MusicBrainz. Return an empty list if the entity is
        not found or another error occurs.

        """
        # check if tag list even exists
        try:
            res = tags[entity]['tag-list']
        except KeyError:
            self.log.debug("No genre found for release group")
            return []
        except Exception as exc:
            self.log.debug("Error in MusicBrainzNgs: {0}", exc)
            return []
        
        # turn object into list of tag names
        res = [el["name"] for el in res]
        return res

    def _last_lookup(self, entity, method, *args, **kwargs):
        """Get a genre based on the named entity using the callable MusicBrainz
        `method` whose arguments are given in the sequence `args`. The genre 
        lookup is cached based on the entity name and the arguments. 
        """
        # if mbentity is None, it is the same as entity
        if 'mbentity' not in kwargs:
            mbentity = entity
        else:
            mbentity = kwargs.get('mbentity')

        # Shortcut if we're missing metadata.
        if any(not s for s in args):
            return None

        key = u'{0}.{1}'.format(entity,
                                u'-'.join(six.text_type(a) for a in args))
        if key in self._genre_cache:
            return self._genre_cache[key]
        else:
            genre = self._tags_for(method(*args, includes=["tags"]), mbentity)
            self._genre_cache[key] = genre
            return genre
