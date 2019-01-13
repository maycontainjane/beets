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
import pylast
import six

from beets import plugins

from . import genrebrowser

LASTFM = pylast.LastFMNetwork(api_key=plugins.LASTFM_KEY)

PYLAST_EXCEPTIONS = (
    pylast.WSError,
    pylast.MalformedResponseError,
    pylast.NetworkError,
)

REPLACE = {
    u'\u2010': '-',
}

class LastFMBrowser(genrebrowser.GenreBrowser):
    """
    Takes in min_weight for tags and logger to log debug messages
    """
    def __init__(self, min_weight, log):
        self.min_weight = min_weight.get(int)
        self.log = log
        self.name = "lastfm"
        super(LastFMBrowser, self).__init__()

    def fetch_album_genre(self, obj):
        """Return the album genre for this Item or Album.
        """
        return self._last_lookup(
            u'album', LASTFM.get_album, obj.albumartist, obj.album
        )

    def fetch_album_artist_genre(self, obj):
        """Return the album artist genre for this Item or Album.
        """
        return self._last_lookup(
            u'artist', LASTFM.get_artist, obj.albumartist
        )

    def fetch_artist_genre(self, item):
        """Returns the track artist genre for this Item.
        """
        return self._last_lookup(
            u'artist', LASTFM.get_artist, item.artist
        )

    def fetch_track_genre(self, obj):
        """Returns the track genre for this Item.
        """
        return self._last_lookup(
            u'track', LASTFM.get_track, obj.artist, obj.title
        )

    def _tags_for(self, obj):
        """Core genre identification routine.

        Given a pylast entity (album or track), return a list of
        tag names for that entity. Return an empty list if the entity is
        not found or another error occurs.

        If `min_weight` is specified, tags are filtered by weight.
        """
        # Work around an inconsistency in pylast where
        # Album.get_top_tags() does not return TopItem instances.
        # https://github.com/pylast/pylast/issues/86
        if isinstance(obj, pylast.Album):
            obj = super(pylast.Album, obj)

        try:
            res = obj.get_top_tags()
        except PYLAST_EXCEPTIONS as exc:
            self.log.debug(u'last.fm error: {0}', exc)
            return []
        except Exception as exc:
            # Isolate bugs in pylast.
            self.log.debug(u'{}', traceback.format_exc())
            self.log.error(u'error in pylast library: {0}', exc)
            return []

        # Filter by weight (optionally).
        if self.min_weight:
            res = [el for el in res if (int(el.weight or 0)) >= self.min_weight]

        # Get strings from tags.
        res = [el.item.get_name().lower() for el in res]
        return res

    def _last_lookup(self, entity, method, *args):
        """Get a genre based on the named entity using the callable `method`
        whose arguments are given in the sequence `args`. The genre lookup
        is cached based on the entity name and the arguments. Before the
        lookup, each argument is has some Unicode characters replaced with
        rough ASCII equivalents in order to return better results from the
        Last.fm database.
        """
        # Shortcut if we're missing metadata.
        if any(not s for s in args):
            return None

        key = u'{0}.{1}'.format(entity,
                                u'-'.join(six.text_type(a) for a in args))
        if key in self._genre_cache:
            return self._genre_cache[key]
        else:
            args_replaced = []
            for arg in args:
                for k, v in REPLACE.items():
                    arg = arg.replace(k, v)
                args_replaced.append(arg)

            genre = self._tags_for(method(*args_replaced))
            self._genre_cache[key] = genre
            return genre
