#!/usr/bin/env python3
"""Forward trie (DAWG) for dictionary-driven move generation.

Nested dict representation:
    node = {letter: child_node, ..., '$': True_if_terminal}

Only A-Z arcs plus the '$' terminal marker. ASCII-safe, pickle-friendly,
and the child-lookup hot path is a single dict membership test.

Public helpers:
    build_trie(words)               -> root
    save_trie(root, path)            write pickle
    load_trie(path)                  read pickle
    load_or_build_trie(dict_path, cache_path) -> root
"""
import pickle
from pathlib import Path


TERMINAL = '$'


def build_trie(words):
    """Build a forward trie from an iterable of uppercase A-Z words."""
    root = {}
    for w in words:
        node = root
        for ch in w:
            child = node.get(ch)
            if child is None:
                child = {}
                node[ch] = child
            node = child
        node[TERMINAL] = True
    return root


def save_trie(root, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'wb') as f:
        pickle.dump(root, f, protocol=pickle.HIGHEST_PROTOCOL)


def load_trie(path):
    with open(path, 'rb') as f:
        return pickle.load(f)


def load_or_build_trie(dict_path, cache_path):
    """Return the trie root. Load from cache_path if it exists; otherwise
    build from dict_path and save to cache_path.

    The dictionary file is treated as static. To force a rebuild, delete
    the cache file.
    """
    cache_path = Path(cache_path)
    if cache_path.exists():
        return load_trie(cache_path)
    dict_path = Path(dict_path)
    with open(dict_path, 'r', encoding='utf-8') as f:
        words = [line.strip().upper() for line in f if line.strip()]
    root = build_trie(words)
    save_trie(root, cache_path)
    return root


def walk(root, word):
    """Return the node reached by walking the arcs of `word`, or None."""
    node = root
    for ch in word:
        node = node.get(ch)
        if node is None:
            return None
    return node


def contains(root, word):
    """True iff `word` is in the trie (terminal node reached)."""
    node = walk(root, word)
    return node is not None and node.get(TERMINAL, False)
