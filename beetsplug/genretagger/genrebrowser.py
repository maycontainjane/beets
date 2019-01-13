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

"""
Generic class for the browsers of various apis
Gets genres from a given source and returns them as a list so that 
genretagger can filter them
"""

class GenreBrowser(object):
    def __init__(self):
        self._genre_cache = {}
        self.name = ""
        super(GenreBrowser, self).__init__()

    def fetch_album_genre(self, obj):
        """Return the album genre for this Item or Album.
        """
        pass

    def fetch_album_artist_genre(self, obj):
        """Return the album artist genre for this Item or Album.
        """
        pass

    def fetch_artist_genre(self, obj):
        """Returns the track artist genre for this Item.
        """
        pass

    def fetch_track_genre(self, obj):
        """Returns the track genre for this Item.
        """
        pass

    def _tags_for(self, obj):
        pass

    def _last_lookup(self, entity, method, *args):
        """Get a genre based on the named entity using the callable `method`
        whose arguments are given in the sequence `args`. The genre lookup
        is cached based on the entity name and the arguments. 
        """
        pass