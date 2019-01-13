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

import wikipedia

from . import genrebrowser

class WikipediaBrowser(object):
    def __init__(self, log):
        self._genre_cache = {}
        self.name = "wikipedia"
        super(WikipediaBrowser, self).__init__()

    def fetch_album_genre(self, obj):
        """Return the album genre for this Item or Album.
        """
        return self._last_lookup(
            u'album', obj.album
        )

    def fetch_album_artist_genre(self, obj):
        """Return the album artist genre for this Item or Album.
        """
        return self._last_lookup(
            u'artist', obj.albumartist
        )

    def fetch_artist_genre(self, item):
        """Returns the track artist genre for this Item.
        """
        return self._last_lookup(
            u'artist', item.artist
        )

    def fetch_track_genre(self, item):
        """Returns the track genre for this Item.
        """
        return self._last_lookup(
            u'track', obj.title
        )

    def _tags_for(self, query, entity):
        """Core genre identification routine.

        Given a pylast entity (album or track), return a list of
        tag names for that entity. Return an empty list if the entity is
        not found or another error occurs.

        If `min_weight` is specified, tags are filtered by weight.
        """
        try:
            res = wikipedia.WikipediaPage(title=query, redirect=True).links
            res = [el.lower() for el in res]
            return res
        except wikipedia.exceptions.PageError:
            self.log.debug("Could not find page for query "+query)
            entity_label = " ("+entity.capitalize()+")"
            print("Trying " +entity_label)
            query = query + entity_label
            try:
                return wikipedia.WikipediaPage(title=query, redirect=True).links
            except wikipedia.exceptions.PageError:
                self.log.debug("Could not find page for query "+query)
                return []

    def _last_lookup(self, entity, query):
        """Get a genre based on the named entity using the callable `method`
        whose arguments are given in the sequence `args`. The genre lookup
        is cached based on the entity name and the arguments. 
        """

        key = u'{0}.{1}'.format(entity,
                                u'-'.join(six.text_type(query)))
        if key in self._genre_cache:
            return self._genre_cache[key]
        else:
            genre = self._tags_for(query, entity)
            self._genre_cache[key] = genre
            return genre
