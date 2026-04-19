#!/usr/bin/env python3
"""GADDAG data structure for bidirectional move generation.

Reference: Steven Gordon, "A Faster Scrabble Move Generation Algorithm"
(1994). The Quackle project (C++) is the canonical open-source
implementation.

Representation: nested dict, same style as wordtrie.py but with two
extra sentinel keys:

    node = {letter_or_sep: child_node, ..., '$': True_if_terminal}

    SEP = '>'         # separator arc, switches from left-walk to right-walk
    TERMINAL = '$'    # marks end-of-variant nodes

Gaddagize(W) for a word of length n produces n "variants":

    for i in 1..n-1:  insert  reverse(W[0:i]) + SEP + W[i:n]
    for i = n:        insert  reverse(W)                 (no SEP)

Example CARE (n=4) inserts:
    C > A R E
    A C > R E
    R A C > E
    E R A C

Each variant is a path from the root ending at a TERMINAL node.

Public helpers:
    gaddagize(word)                 -> list[str]   variants to insert
    build_gaddag(words)             -> root        root dict
    save_gaddag(root, path)          pickle dump
    load_gaddag(path)                pickle load
    load_or_build_gaddag(dict_path, cache_path) -> root
"""
import pickle
from pathlib import Path


SEP = '>'
TERMINAL = '$'


def gaddagize(word):
    """Return the list of GADDAG variants for `word`.

    Each variant is a string over {A-Z, SEP}. The final variant (i=n)
    is just the full reversed word without a trailing SEP.
    """
    n = len(word)
    out = []
    for i in range(1, n):
        out.append(word[:i][::-1] + SEP + word[i:])
    out.append(word[::-1])
    return out


def build_gaddag(words):
    """Build a GADDAG from an iterable of uppercase A-Z words."""
    root = {}
    for w in words:
        for variant in gaddagize(w):
            node = root
            for ch in variant:
                child = node.get(ch)
                if child is None:
                    child = {}
                    node[ch] = child
                node = child
            node[TERMINAL] = True
    return root


def save_gaddag(root, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'wb') as f:
        pickle.dump(root, f, protocol=pickle.HIGHEST_PROTOCOL)


def load_gaddag(path):
    with open(path, 'rb') as f:
        return pickle.load(f)


def load_or_build_gaddag(dict_path, cache_path):
    """Return the GADDAG root. Load from cache_path if it exists;
    otherwise build from dict_path and save to cache_path.

    The dictionary file is treated as static. To force a rebuild,
    delete the cache file.
    """
    cache_path = Path(cache_path)
    if cache_path.exists():
        return load_gaddag(cache_path)
    dict_path = Path(dict_path)
    with open(dict_path, 'r', encoding='utf-8') as f:
        words = [line.strip().upper() for line in f if line.strip()]
    root = build_gaddag(words)
    save_gaddag(root, cache_path)
    return root


def walk(root, path):
    """Return the node reached by walking the arcs of `path`, or None."""
    node = root
    for ch in path:
        node = node.get(ch)
        if node is None:
            return None
    return node


def contains(root, path):
    """True iff the trie has a terminal at the end of `path`."""
    node = walk(root, path)
    return node is not None and node.get(TERMINAL, False)
