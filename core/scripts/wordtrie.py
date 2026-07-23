#!/usr/bin/env python3
"""Forward trie for dictionary-driven move generation.

Nested dict representation:
    node = {letter: child_node, ..., '$': True_if_terminal}

Only A-Z arcs plus the '$' terminal marker. The child-lookup hot path is a
single dict membership test.

Public helpers:
    build_trie(words)               -> root
"""


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
