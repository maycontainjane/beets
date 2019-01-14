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

from __future__ import division, absolute_import, print_function
import six

"""Gets genres for imported music based on Last.fm tags.

Uses a provided whitelist file to determine which tags are valid genres.
The included (default) genre list was originally produced by scraping Wikipedia
and has been edited to remove some questionable entries.
The scraper script used is available here:
https://gist.github.com/1241307
"""
import pylast
import codecs
import os
import yaml
import traceback

from . import lastbrowser
from . import mbbrowser
from . import wikibrowser

from beets import plugins
from beets import ui
from beets import config
from beets.util import normpath, plurality
from beets import library


def deduplicate(seq):
    """Remove duplicates from sequence wile preserving order.
    """
    seen = set()
    return [x for x in seq if x not in seen and not seen.add(x)]


# Canonicalization tree processing.

def flatten_tree(elem, path, branches):
    """Flatten nested lists/dictionaries into lists of strings
    (branches).
    """
    if not path:
        path = []

    if isinstance(elem, dict):
        for (k, v) in elem.items():
            flatten_tree(v, path + [k], branches)
    elif isinstance(elem, list):
        for sub in elem:
            flatten_tree(sub, path, branches)
    else:
        branches.append(path + [six.text_type(elem)])


def find_parents(candidate, branches):
    """Find parents genre of a given genre, ordered from the closest to
    the further parent.
    """
    for branch in branches:
        try:
            idx = branch.index(candidate.lower())
            return list(reversed(branch[:idx + 1]))
        except ValueError:
            continue
    return [candidate]


# Main plugin logic.

WHITELIST = os.path.join(os.path.dirname(__file__), 'genres.txt')
C14N_TREE = os.path.join(os.path.dirname(__file__), 'genres-tree.yaml')


class GenreTaggerPlugin(plugins.BeetsPlugin):
    def __init__(self):
        super(GenreTaggerPlugin, self).__init__()

        self.config.add({
            'whitelist': True,
            'count': 5,
            'fallback': None,
            'min_weight': 10,
            'canonical': False,
            'source': 'album',
            'force': True,
            'auto': True,
            'separator': u', ',
            'prefer_specific': False
        })

        self.setup()

    def setup(self):
        """Setup plugin from config options
        """
        if self.config['auto']:
            self.import_stages = [self.imported]

        self._genre_cache = {}

        # Read the whitelist file if enabled.
        self.whitelist = set()
        wl_filename = self.config['whitelist'].get()
        if wl_filename in (True, ''):  # Indicates the default whitelist.
            wl_filename = WHITELIST
        if wl_filename:
            wl_filename = normpath(wl_filename)
            with open(wl_filename, 'rb') as f:
                for line in f:
                    line = line.decode('utf-8').strip().lower()
                    if line and not line.startswith(u'#'):
                        self.whitelist.add(line)

        # Read the genres tree for canonicalization if enabled.
        self.c14n_branches = []
        c14n_filename = self.config['canonical'].get()
        self.canonicalize = c14n_filename is not False

        # Default tree
        if c14n_filename in (True, ''):
            c14n_filename = C14N_TREE
        elif not self.canonicalize and self.config['prefer_specific'].get():
            # prefer_specific requires a tree, load default tree
            c14n_filename = C14N_TREE

        # Read the tree
        if c14n_filename:
            self._log.debug('Loading canonicalization tree {0}', c14n_filename)
            c14n_filename = normpath(c14n_filename)
            with codecs.open(c14n_filename, 'r', encoding='utf-8') as f:
                genres_tree = yaml.load(f)
            flatten_tree(genres_tree, [], self.c14n_branches)

    @property
    def sources(self):
        """A tuple of allowed genre sources. May contain 'track',
        'album', or 'artist.'
        """
        source = self.config['source'].as_choice(('track', 'album', 'artist'))
        if source == 'track':
            return 'track', 'album', 'artist'
        elif source == 'album':
            return 'album', 'artist'
        elif source == 'artist':
            return 'artist',

    def _get_depth(self, tag):
        """Find the depth of a tag in the genres tree.
        """
        depth = None
        for key, value in enumerate(self.c14n_branches):
            if tag in value:
                depth = value.index(tag)
                break
        return depth

    def _sort_by_depth(self, tags):
        """Given a list of tags, sort the tags by their depths in the
        genre tree.
        """
        depth_tag_pairs = [(self._get_depth(t), t) for t in tags]
        depth_tag_pairs = [e for e in depth_tag_pairs if e[0] is not None]
        depth_tag_pairs.sort(reverse=True)
        return [p[1] for p in depth_tag_pairs]

    def _resolve_genres(self, tags):
        """Given a list of strings, return a genre by joining them into a
        single string and (optionally) canonicalizing each.
        """
        if not tags:
            return None

        count = self.config['count'].get(int)
        if self.canonicalize:
            # Extend the list to consider tags parents in the c14n tree
            tags_all = []
            for tag in tags:
                # Add parents that are in the whitelist, or add the oldest
                # ancestor if no whitelist
                if self.whitelist:
                    parents = [x for x in find_parents(tag, self.c14n_branches)
                               if self._is_allowed(x)]
                else:
                    parents = [find_parents(tag, self.c14n_branches)[-1]]

                tags_all += parents
                # Stop if we have enough tags already, unless we need to find
                # the most specific tag (instead of the most popular).
                if (not self.config['prefer_specific'] and
                        len(tags_all) >= count):
                    break
            tags = tags_all

        tags = deduplicate(tags)

        # Sort the tags by specificity.
        if self.config['prefer_specific']:
            tags = self._sort_by_depth(tags)

        # c14n only adds allowed genres but we may have had forbidden genres in
        # the original tags list
        tags = [x.title() for x in tags if self._is_allowed(x)]

        return self.config['separator'].as_str().join(
            tags[:self.config['count'].get(int)]
        )

    def _is_allowed(self, genre):
        """Determine whether the genre is present in the whitelist,
        returning a boolean.
        """
        if genre is None:
            return False
        if not self.whitelist or genre in self.whitelist:
            return True
        return False

    def _get_genre(self, obj):
        """Get the genre string for an Album or Item object based on
        self.sources, using browsers in order of preference. 
        Return a `(genre, source)` pair. The
        prioritization order is:
            - track (for Items only)
            - album
            - artist
            - original
            - fallback
            - None
        """

        # Shortcut to existing genre if not forcing.
        if not self.config['force'] and self._is_allowed(obj.genre):
            return obj.genre, 'keep'

        for browsername in self.config['preferred_order'].get():
            if browsername == "lastfm":
                browser = lastbrowser.LastFMBrowser(self.config['min_weight'], self._log)
                self._log.info("Using lastfm to fetch genre")
            elif browsername == "musicbrainz":
                browser = mbbrowser.MusicBrainzBrowser(self._log)
                self._log.info("Using musicbrainz to fetch genre")
            elif browsername == "wikipedia":
                browser = wikibrowser.WikipediaBrowser(self._log)
                self._log.info("Using wikipedia to fetch genre")
            else:
                self._log.debug("Browser {0} does not exist", browsername)
                return None, None

            res = self._browse_for_genre(obj, browser)
            if res != (None, None) and res[0] != [] and res[0] != '' and res != None:
                return res

    def _browse_for_genre(self, obj, browser):
         # Track genre (for Items only).
        if isinstance(obj, library.Item):
            if 'track' in self.sources:
                result = browser.fetch_track_genre(obj)
                if result:
                    return self._resolve_genres(result), 'track'

        # Album genre.
        if 'album' in self.sources:
            result = browser.fetch_album_genre(obj)
            if result:
                return self._resolve_genres(result), 'album'

        # Artist (or album artist) genre.
        if 'artist' in self.sources:
            result = None
            if isinstance(obj, library.Item):
                result = browser.fetch_artist_genre(obj)
            elif obj.albumartist != config['va_name'].as_str():
                result = browser.fetch_album_artist_genre(obj)
            else:
                # For "Various Artists", pick the most popular track genre.
                item_genres = []
                for item in obj.items():
                    item_genre = None
                    if 'track' in self.sources:
                        item_genre = browser.fetch_track_genre(item)
                    if not item_genre:
                        item_genre = browser.fetch_artist_genre(item)
                    if item_genre:
                        item_genres.append(item_genre)
                if item_genres:
                    result, _ = plurality(item_genres)
            if result:
                return self._resolve_genres(result), 'artist'
        # Filter the existing genre.
        if obj.genre:
            result = self._resolve_genres([obj.genre])
            if result:
                return self._resolve_genres(result), 'original'

        # Fallback string.
        fallback = self.config['fallback'].get()
        if fallback:
            return fallback, 'fallback'
        return None, None

    def commands(self):
        genretagger_cmd = ui.Subcommand('genretagger', help=u'fetch genres')
        genretagger_cmd.parser.add_option(
            u'-f', u'--force', dest='force',
            action='store_true', default=False,
            help=u're-download genre when already present'
        )
        genretagger_cmd.parser.add_option(
            u'-s', u'--source', dest='source', type='string',
            help=u'genre source: artist, album, or track'
        )

        def genretagger_func(lib, opts, args):
            write = ui.should_write()
            self.config.set_args(opts)

            for album in lib.albums(ui.decargs(args)):
                try:
                    album.genre, src = self._get_genre(album)
                    self._log.info(u'genre for album {0} ({1}): {0.genre}',
                                   album, src)
                    album.store()

                    for item in album.items():
                        # If we're using track-level sources, also look up each
                        # track on the album.
                        if 'track' in self.sources:
                            item.genre, src = self._get_genre(item)
                            item.store()
                            self._log.info(u'genre for track {0} ({1}): {0.genre}',
                                           item, src)

                        if write:
                            item.try_write()
                # if _get_genres returns none, none fo the sources returned any genre info
                except TypeError:
                    self._log.info(u'Unable to find any genre info for {0} from {1}.', album, self.config['preferred_order'])

        genretagger_cmd.func = genretagger_func
        return [genretagger_cmd]

    def imported(self, session, task):
        """Event hook called when an import task finishes."""
        try:
            if task.is_album:
                    album = task.album
                    album.genre, src = self._get_genre(album)
                    self._log.debug(u'added album genre ({0}): {1}',
                                    src, album.genre)
                    album.store()

                    if 'track' in self.sources:
                        for item in album.items():
                            item.genre, src = self._get_genre(item)
                            self._log.debug(u'added item genre ({0}): {1}',
                                            src, item.genre)
                            item.store() 

            else:
                item = task.item
                item.genre, src = self._get_genre(item)
                self._log.debug(u'added item genre ({0}): {1}',
                                src, item.genre)
                item.store()
        except TypeError:
            self._log.info(u'Unable to find any genre info for {0} from {1}.', album, self.config['preferred_order'])
