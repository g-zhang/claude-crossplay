#!/usr/bin/env python3
"""
NYT Crossplay Board Solver

Usage:
    python solver.py --board board.json --rack AILETEC --dict dict.txt [--top 20] [--full-board]
    python solver.py --board board.json --dict dict.txt --rack X --confirm-only

board.json format: {"row,col": "LETTER", ...}
  Use lowercase for blank tiles (0 pts): {"7,8": "k"}

Or pass a 15-line text board via --board-text board.txt
"""
import json
import sys
import argparse
import time
import copy
import heapq
from collections import Counter
from pathlib import Path

import wordtrie
import gaddag as gaddag_mod

# ============================================================
# NYT Crossplay Tile Scores
# Differences from Scrabble: G=4, J=10, V=6, B=4, K=6, L=2,
#   U=2, W=5, H=3
# ============================================================
TILE_PTS = {
    'A':1,'B':4,'C':3,'D':2,'E':1,'F':4,'G':4,'H':3,'I':1,
    'J':10,'K':6,'L':2,'M':3,'N':1,'O':1,'P':3,'Q':10,'R':1,
    'S':1,'T':1,'U':2,'V':6,'W':5,'X':8,'Y':4,'Z':10,'?':0
}

# Blank expansion order: English letter frequency (desc). Iterating ? candidates
# in this order finds valid moves earlier -> B&B top-N heap fills faster -> more
# pruning. Also produces better partial results when a time limit fires.
BLANK_LETTER_ORDER = "ETAOINSHRDLCUMWFGYPBVKJXQZ"


class _TimeLimit(Exception):
    """Raised inside _build to unwind when the solver deadline is reached."""
    pass

# ============================================================
# NYT Crossplay Premium Squares (from empty board image analysis)
# 56 total: 8x3W, 8x2W, 20x3L, 20x2L -- fully symmetric
# Center (7,7) has no premium.
# ============================================================
PREMIUM = {}
for p in [(0,3),(0,11),(3,0),(3,14),(11,0),(11,14),(14,3),(14,11)]:
    PREMIUM[p] = 'TW'
for p in [(1,1),(1,13),(3,7),(7,3),(7,11),(11,7),(13,1),(13,13)]:
    PREMIUM[p] = 'DW'
for p in [(0,0),(0,14),(1,6),(1,8),
          (4,5),(4,9),(5,4),(5,10),
          (6,1),(6,13),(8,1),(8,13),
          (9,4),(9,10),(10,5),(10,9),
          (13,6),(13,8),(14,0),(14,14)]:
    PREMIUM[p] = 'TL'
for p in [(0,7),(2,4),(2,10),(3,3),(3,11),(4,2),(4,12),(5,7),
          (7,0),(7,5),(7,9),(7,14),(9,7),(10,2),(10,12),(11,3),
          (11,11),(12,4),(12,10),(14,7)]:
    PREMIUM[p] = 'DL'

# Map internal codes to display labels
PREMIUM_DISPLAY = {'TW':'3W','DW':'2W','TL':'3L','DL':'2L'}

# Precomputed bit mask per letter; saves ord()-on-every-step in hot loops.
LETTER_BIT = {chr(ord('A') + i): 1 << i for i in range(26)}


def load_dictionary(dict_path):
    """Load dictionary and build prefix set."""
    words = set()
    with open(dict_path, encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            raw_word = line.strip()
            if not raw_word:
                continue
            if not raw_word.isascii() or not raw_word.isalpha():
                raise ValueError(
                    f"Dictionary line {line_number} is not an A-Z word: "
                    f"{raw_word!r}"
                )
            if not 2 <= len(raw_word) <= 15:
                raise ValueError(
                    f"Dictionary line {line_number} must contain 2 to 15 letters"
                )
            words.add(raw_word.upper())
    if not words:
        raise ValueError("Dictionary contains no words")
    prefixes = set()
    for w in words:
        for i in range(1, len(w)+1):
            prefixes.add(w[:i])
    return words, prefixes


def normalize_board_tiles(data):
    """Validate board JSON data and return canonical coordinate keys."""
    if not isinstance(data, dict):
        raise ValueError("Board JSON must be an object")
    tiles = data.get("tiles", data)
    if not isinstance(tiles, dict):
        raise ValueError("Board JSON 'tiles' must be an object")

    normalized = {}
    blank_count = 0
    for key, letter in tiles.items():
        if not isinstance(key, str):
            raise ValueError("Board coordinate keys must be 'row,col' strings")
        parts = key.split(",")
        if len(parts) != 2:
            raise ValueError(f"Invalid board coordinate {key!r}; expected 'row,col'")
        try:
            row, col = (int(part.strip()) for part in parts)
        except ValueError as exc:
            raise ValueError(
                f"Invalid board coordinate {key!r}; row and column must be integers"
            ) from exc
        if not 0 <= row < 15 or not 0 <= col < 15:
            raise ValueError(
                f"Board coordinate {key!r} is outside the 15x15 board"
            )
        if (
                not isinstance(letter, str)
                or len(letter) != 1
                or not letter.isascii()
                or not letter.isalpha()):
            raise ValueError(
                f"Tile at ({row},{col}) must be one ASCII letter"
            )

        canonical_key = f"{row},{col}"
        if canonical_key in normalized:
            raise ValueError(
                f"Duplicate board coordinate after normalization: {canonical_key}"
            )
        normalized[canonical_key] = letter
        if letter.islower():
            blank_count += 1

    if blank_count > 3:
        raise ValueError("Crossplay boards cannot contain more than three blanks")
    return normalized


def load_board_json(path):
    """Load board from JSON format. Lowercase letters = blank tiles (0 pts)."""
    board = [['.']*15 for _ in range(15)]
    blanks = set()
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    for key, letter in normalize_board_tiles(data).items():
        r, c = (int(part) for part in key.split(","))
        if letter.islower():
            blanks.add((r, c))
        board[r][c] = letter.upper()
    return board, blanks


def load_board_text(path):
    """Load board from 15-line text file (. = empty). Lowercase = blank."""
    board = [['.']*15 for _ in range(15)]
    blanks = set()
    with open(path, encoding="utf-8") as f:
        lines = f.read().splitlines()
    if len(lines) != 15:
        raise ValueError(
            f"Board text must contain exactly 15 lines; found {len(lines)}"
        )
    for r, line in enumerate(lines):
        if len(line) != 15:
            raise ValueError(
                f"Board text row {r} must contain exactly 15 characters"
            )
        for c, ch in enumerate(line):
            if ch == '.':
                continue
            if not ch.isascii() or not ch.isalpha():
                raise ValueError(
                    f"Board text tile at ({r},{c}) must be '.' or an ASCII letter"
                )
            if ch.islower():
                blanks.add((r, c))
            board[r][c] = ch.upper()
    if len(blanks) > 3:
        raise ValueError("Crossplay boards cannot contain more than three blanks")
    return board, blanks


def validate_rack(rack):
    """Return an uppercase rack after validating Crossplay tile syntax."""
    if not isinstance(rack, str) or not 1 <= len(rack) <= 7:
        raise ValueError("Rack must contain between one and seven tiles")
    if any(
            ch != '?' and (not ch.isascii() or not ch.isalpha())
            for ch in rack):
        raise ValueError("Rack may contain only A-Z letters and '?' blanks")
    normalized = rack.upper()
    if normalized.count('?') > 3:
        raise ValueError("A Crossplay rack cannot contain more than three blanks")
    return list(normalized)


def print_board(board, new_tiles=None, file=sys.stdout):
    """Simple board print (no premium squares)."""
    if new_tiles is None:
        new_tiles = set()
    print("     " + "  ".join(f"{i:2d}" for i in range(15)), file=file)
    print("    " + "-"*47, file=file)
    for r in range(15):
        row_str = f"{r:2d} |"
        for c in range(15):
            ch = board[r][c]
            if (r,c) in new_tiles:
                row_str += f" [{ch}]"
            elif ch != '.':
                row_str += f"  {ch} "
            else:
                row_str += "  . "
        print(row_str, file=file)


def print_full_board(board, new_tiles=None, blanks=None, file=sys.stdout):
    """Print full board with premium squares, tiles, and new tiles in brackets."""
    if new_tiles is None:
        new_tiles = {}
    if blanks is None:
        blanks = set()
    print("      0    1    2    3    4    5    6    7    8    9   10   11   12   13   14", file=file)
    print("    " + "-" * 75, file=file)
    for r in range(15):
        row = f"{r:2d} |"
        for c in range(15):
            if (r,c) in new_tiles:
                row += f" [{new_tiles[(r,c)]}]  "
            elif board[r][c] != '.':
                if (r,c) in blanks:
                    row += f"  {board[r][c].lower()}   "
                else:
                    row += f"  {board[r][c]}   "
            elif (r,c) == (7,7):
                row += "  *   "
            elif (r,c) in PREMIUM:
                row += f" {PREMIUM_DISPLAY[PREMIUM[(r,c)]]:>2s}  "
            else:
                row += "  .   "
        print(row, file=file)


def format_blank_inventory(board, blanks):
    """Describe blank metadata without implying it was image-verified."""
    if blanks:
        marked = ", ".join(
            f"{board[r][c]}@({r},{c})"
            for r, c in sorted(blanks)
        )
        status = f"marked as 0-point blanks: {marked}."
    else:
        status = "no 0-point blanks marked."

    reminder = (
        "Verify against the tile-audit score corners: every displayed 0 "
        "must be lowercase in board JSON, and every lowercase tile must "
        "display 0."
    )
    if len(blanks) > 3:
        reminder += " WARNING: Crossplay has only three blank tiles."
    return f"Blank audit: {status} {reminder}"


# ============================================================
# Core solver
# ============================================================
class BoardSolver:
    def __init__(self, board, rack, valid_words, prefixes, blanks=None,
                 top_n=10, time_limit=0, no_prune=False,
                 engine='trie', trie=None, gaddag=None):
        self.board = board
        self.rack = rack
        self.valid_words = valid_words
        self.prefixes = prefixes
        self.blanks = blanks or set()
        self.moves = []
        # B&B + timer config
        self.top_n = top_n
        self.time_limit = time_limit  # seconds; 0 = unlimited
        self.no_prune = no_prune
        self.deadline = None          # set in find_all_moves
        self.top_heap = []            # min-heap of accepted-move scores (size <= top_n)
        self.max_cross = {}           # (r,c,dir) -> upper bound on cross-word score
        self.cross_masks = {}         # (r,c,dir) -> 26-bit mask of legal cross letters
        self.timed_out = False
        # Engine selection
        self.engine = engine          # 'trie' (default), 'gaddag', or 'naive'
        self.trie = trie              # root dict if engine == 'trie'
        self.gaddag = gaddag          # root dict if engine == 'gaddag'

    def get_word_at(self, r, c, dr, dc):
        """Get the full word passing through (r,c) in direction (dr,dc)."""
        sr, sc = r, c
        while (sr-dr >= 0 and sc-dc >= 0 and sr-dr < 15 and sc-dc < 15
               and self.board[sr-dr][sc-dc] != '.'):
            sr -= dr; sc -= dc
        word = ""
        cr, cc = sr, sc
        while 0 <= cr < 15 and 0 <= cc < 15 and self.board[cr][cc] != '.':
            word += self.board[cr][cc]
            cr += dr; cc += dc
        return word, sr, sc

    def verify_and_score(self, placements, direction):
        """Verify a move and calculate its score.

        placements is list of (r, c, letter). Lowercase letter means the tile
        came from a rack blank (scored 0, no premium); letters are uppercased
        on the board during lookup so dict checks are case-insensitive.
        """
        if not placements:
            return False, 0, '', []

        dr = 0 if direction == 'H' else 1
        dc = 1 if direction == 'H' else 0
        cdr, cdc = 1-dr, 1-dc

        # Blanks placed this turn (tracked by lowercase letter in placements)
        placed_blanks = {(r, c) for r, c, letter in placements if letter.islower()}
        all_blanks = self.blanks | placed_blanks

        # Temporarily place tiles (always uppercase on the board)
        for r, c, letter in placements:
            self.board[r][c] = letter.upper()

        # Get main word
        r0, c0 = placements[0][0], placements[0][1]
        main_word, sr, sc = self.get_word_at(r0, c0, dr, dc)

        valid = True
        if len(main_word) < 2 or main_word not in self.valid_words:
            valid = False

        # Check cross words
        cross_words = []
        if valid:
            for r, c, letter in placements:
                cw, csr, csc = self.get_word_at(r, c, cdr, cdc)
                if len(cw) >= 2:
                    cross_words.append((cw, csr, csc))
                    if cw not in self.valid_words:
                        valid = False
                        break

        # Check connectivity
        touches_existing = False
        placement_set = {(p[0], p[1]) for p in placements}
        board_empty = all(self.board[r][c] == '.' for r in range(15)
                         for c in range(15) if (r,c) not in placement_set)
        if board_empty and (7,7) in placement_set:
            touches_existing = True
        else:
            for r, c, _ in placements:
                for ddr, ddc in [(-1,0),(1,0),(0,-1),(0,1)]:
                    nr, nc = r+ddr, c+ddc
                    if (0<=nr<15 and 0<=nc<15 and self.board[nr][nc] != '.'
                        and (nr,nc) not in placement_set):
                        touches_existing = True
                        break
                if touches_existing:
                    break
            if not touches_existing:
                cr, cc = sr, sc
                while 0<=cr<15 and 0<=cc<15 and self.board[cr][cc] != '.':
                    if (cr,cc) not in placement_set:
                        touches_existing = True
                        break
                    cr += dr; cc += dc
        if not touches_existing:
            valid = False

        # Calculate score
        score = 0
        if valid:
            # Main word score
            mw_score = 0; mw_mult = 1
            cr, cc = sr, sc
            for ch in main_word:
                pts = 0 if (cr, cc) in all_blanks else TILE_PTS.get(ch, 0)
                if (cr, cc) in placement_set:
                    pm = PREMIUM.get((cr, cc), '')
                    if pm == 'DL': pts *= 2
                    elif pm == 'TL': pts *= 3
                    elif pm == 'DW': mw_mult *= 2
                    elif pm == 'TW': mw_mult *= 3
                mw_score += pts
                cr += dr; cc += dc
            score += mw_score * mw_mult

            # Cross word scores
            for cw, csr, csc in cross_words:
                cw_score = 0; cw_mult = 1
                cr, cc = csr, csc
                for ch in cw:
                    pts = 0 if (cr, cc) in all_blanks else TILE_PTS.get(ch, 0)
                    if (cr, cc) in placement_set:
                        pm = PREMIUM.get((cr, cc), '')
                        if pm == 'DL': pts *= 2
                        elif pm == 'TL': pts *= 3
                        elif pm == 'DW': cw_mult *= 2
                        elif pm == 'TW': cw_mult *= 3
                    cw_score += pts
                    cr += cdr; cc += cdc
                score += cw_score * cw_mult

            # 7-tile bonus (40 pts for Crossplay)
            if len(placements) == 7:
                score += 40

        # Remove temporary tiles
        for r, c, letter in placements:
            self.board[r][c] = '.'

        return valid, score, main_word, cross_words

    def _score_only(self, placements, direction):
        """Score a placement without revalidating word/connectivity.

        Caller MUST guarantee:
          1. main_word is in valid_words (trie/gaddag terminal nodes do)
          2. every cross word is in valid_words (cross_masks built from
             valid_words enforce this)
          3. placements include the anchor cell, so connectivity to the
             rest of the board is implicit (or anchor is the synthetic
             (7,7) first-move case)

        Used by trie/gaddag paths where validation is a redundant
        ~37%-of-runtime cost (M0 profile finding). Returns
        (score, main_word, cross_words). Score is 0 if the move is
        somehow invalid (defensive; should not happen with a correct
        caller).
        """
        if not placements:
            return 0, '', []

        dr = 0 if direction == 'H' else 1
        dc = 1 if direction == 'H' else 0
        cdr, cdc = 1 - dr, 1 - dc

        placed_blanks = {(r, c) for r, c, letter in placements
                         if letter.islower()}
        all_blanks = self.blanks | placed_blanks
        placement_set = {(p[0], p[1]) for p in placements}

        for r, c, letter in placements:
            self.board[r][c] = letter.upper()

        r0, c0 = placements[0][0], placements[0][1]
        main_word, sr, sc = self.get_word_at(r0, c0, dr, dc)

        cross_words = []
        for r, c, letter in placements:
            cw, csr, csc = self.get_word_at(r, c, cdr, cdc)
            if len(cw) >= 2:
                cross_words.append((cw, csr, csc))

        # Main word score
        score = 0
        mw_score = 0
        mw_mult = 1
        cr, cc = sr, sc
        for ch in main_word:
            pts = 0 if (cr, cc) in all_blanks else TILE_PTS.get(ch, 0)
            if (cr, cc) in placement_set:
                pm = PREMIUM.get((cr, cc), '')
                if pm == 'DL':
                    pts *= 2
                elif pm == 'TL':
                    pts *= 3
                elif pm == 'DW':
                    mw_mult *= 2
                elif pm == 'TW':
                    mw_mult *= 3
            mw_score += pts
            cr += dr
            cc += dc
        score += mw_score * mw_mult

        # Cross word scores
        for cw, csr, csc in cross_words:
            cw_score = 0
            cw_mult = 1
            cr, cc = csr, csc
            for ch in cw:
                pts = 0 if (cr, cc) in all_blanks else TILE_PTS.get(ch, 0)
                if (cr, cc) in placement_set:
                    pm = PREMIUM.get((cr, cc), '')
                    if pm == 'DL':
                        pts *= 2
                    elif pm == 'TL':
                        pts *= 3
                    elif pm == 'DW':
                        cw_mult *= 2
                    elif pm == 'TW':
                        cw_mult *= 3
                cw_score += pts
                cr += cdr
                cc += cdc
            score += cw_score * cw_mult

        if len(placements) == 7:
            score += 40

        for r, c, letter in placements:
            self.board[r][c] = '.'

        return score, main_word, cross_words

    def _precompute_max_cross(self):
        """For each empty cell and each play direction, compute an upper bound
        on the cross-word score any tile placed there could generate. Used by
        B&B upper-bound pruning in _build.

        Takes max over A-Z -- this is safe: any actual placement (including a
        rack blank, which scores 0 for the placed letter) produces a score <=
        this max.
        """
        self.max_cross = {}
        for r in range(15):
            for c in range(15):
                if self.board[r][c] != '.':
                    continue
                for direction in ('H', 'V'):
                    cdr, cdc = (1, 0) if direction == 'H' else (0, 1)
                    has_above = (r - cdr >= 0 and c - cdc >= 0
                                 and self.board[r - cdr][c - cdc] != '.')
                    has_below = (r + cdr < 15 and c + cdc < 15
                                 and self.board[r + cdr][c + cdc] != '.')
                    if not (has_above or has_below):
                        self.max_cross[(r, c, direction)] = 0
                        continue
                    pm = PREMIUM.get((r, c), '')
                    letter_mult = 3 if pm == 'TL' else 2 if pm == 'DL' else 1
                    word_mult = 3 if pm == 'TW' else 2 if pm == 'DW' else 1
                    best = 0
                    for letter in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
                        self.board[r][c] = letter
                        cw, csr, csc = self.get_word_at(r, c, cdr, cdc)
                        if len(cw) >= 2 and cw in self.valid_words:
                            score = self._cross_score_for_placement(
                                r, c, cdr, cdc, csr, csc,
                                TILE_PTS[letter], letter_mult, word_mult)
                            if score > best:
                                best = score
                    self.board[r][c] = '.'
                    self.max_cross[(r, c, direction)] = best

    def _precompute_cross_masks(self):
        """For each empty cell and each main-word direction, compute a
        26-bit int mask where bit (L - 'A') is set iff placing letter L
        here forms a valid cross-word in the perpendicular direction.

        For cells with no perpendicular neighbor, no cross-word is formed
        by any placement -- mask is all bits set (any letter is legal).

        Distinct from max_cross: this is a legality mask, not a score. It
        is used by the --engine trie path to prune placements whose
        cross-word would be invalid, without having to score or even
        string-match inside _build_trie.
        """
        ALL_BITS = (1 << 26) - 1
        self.cross_masks = {}
        # Flat 15x15 lists for hot-path access (opt-B). H plane = mask
        # used when the main-word direction is H. Default 0 (filled cell
        # never placed on; loop guards prevent access there anyway).
        self.cross_masks_h = [[0]*15 for _ in range(15)]
        self.cross_masks_v = [[0]*15 for _ in range(15)]
        for r in range(15):
            for c in range(15):
                if self.board[r][c] != '.':
                    continue
                for direction in ('H', 'V'):
                    cdr, cdc = (1, 0) if direction == 'H' else (0, 1)
                    has_above = (r - cdr >= 0 and c - cdc >= 0
                                 and self.board[r - cdr][c - cdc] != '.')
                    has_below = (r + cdr < 15 and c + cdc < 15
                                 and self.board[r + cdr][c + cdc] != '.')
                    if not (has_above or has_below):
                        self.cross_masks[(r, c, direction)] = ALL_BITS
                        if direction == 'H':
                            self.cross_masks_h[r][c] = ALL_BITS
                        else:
                            self.cross_masks_v[r][c] = ALL_BITS
                        continue
                    mask = 0
                    for i in range(26):
                        letter = chr(ord('A') + i)
                        self.board[r][c] = letter
                        cw, _, _ = self.get_word_at(r, c, cdr, cdc)
                        if len(cw) >= 2 and cw in self.valid_words:
                            mask |= (1 << i)
                    self.board[r][c] = '.'
                    self.cross_masks[(r, c, direction)] = mask
                    if direction == 'H':
                        self.cross_masks_h[r][c] = mask
                    else:
                        self.cross_masks_v[r][c] = mask

    def _precompute_left_limits(self, anchors):
        """Appel-Jacobson per-anchor left-extent limits.

        For each anchor (r, c) and each main-word direction, count the
        number of tiles that may be PLACED strictly to the left of the
        anchor along the main axis. The scan walks leftward one cell at
        a time, starting at the cell immediately left of the anchor:

          * stop on another anchor cell (don't count it);
          * skip filled cells (don't count, don't stop) -- walked-through
            existing tiles are pre-main-word prefix, not placements;
          * increment on empty non-anchor cells;
          * stop at the board edge.

        Stored as self.left_limits[(r, c, direction)] -> int >= 0.
        """
        self.left_limits = {}
        for ar, ac in anchors:
            for direction in ('H', 'V'):
                dr, dc = (0, 1) if direction == 'H' else (1, 0)
                count = 0
                r, c = ar - dr, ac - dc
                while 0 <= r < 15 and 0 <= c < 15:
                    if (r, c) in anchors:
                        break
                    if self.board[r][c] == '.':
                        count += 1
                    # Filled cell: skip without incrementing or breaking.
                    r -= dr
                    c -= dc
                self.left_limits[(ar, ac, direction)] = count

    def _cross_score_for_placement(self, r, c, cdr, cdc, csr, csc,
                                   letter_val, letter_mult, word_mult):
        """Score a cross-word formed by placing a tile at (r,c). Caller is
        responsible for having verified cw is valid (length >= 2, in dict).

        letter_val is the new tile's raw points (0 for blank). letter_mult is
        the letter premium multiplier at (r,c). word_mult is the word premium
        multiplier at (r,c) (DW/TW, only applied from this new tile).

        Board is assumed to have the placed letter set at (r,c) OR not -- we
        don't read board[r][c]; we use letter_val directly.
        """
        total = letter_val * letter_mult
        cr, cc = csr, csc
        while 0 <= cr < 15 and 0 <= cc < 15 and self.board[cr][cc] != '.':
            if (cr, cc) != (r, c):
                if (cr, cc) not in self.blanks:
                    total += TILE_PTS[self.board[cr][cc]]
            cr += cdr; cc += cdc
        return total * word_mult

    def _compute_ub(self, r, c, dr, dc, direction, rack_left, placements,
                    main_base, main_mult, cross_total):
        """Upper bound on the best achievable score from this _build state.

        Walks forward from (r,c) in the scan direction, tabulating:
        - existing_ahead_value: fixed letter values at existing tiles we'd pass
        - empty_ahead_count: cells we could place a new tile on
        - letter_mults_ahead, word_mult_ahead: premium contributions
        - cross_sum: Sum  max_cross[cell][direction] over empty cells ahead
        Then pairs the top-k rack letter values with the top-k letter
        multipliers greedily for an optimal per-rearrangement-inequality
        upper bound on main-word letter score from future placements.
        """
        rack_room = sum(rack_left.values())
        existing_ahead_value = 0
        empty_ahead_mults = []  # (letter_mult, word_mult, max_cross)
        cross_sum = 0
        word_mult_ahead = 1
        cr, cc = r, c
        placements_left = rack_room
        while 0 <= cr < 15 and 0 <= cc < 15:
            if self.board[cr][cc] == '.':
                if placements_left == 0:
                    # Main word terminates at this gap; no more extension possible.
                    break
                pm = PREMIUM.get((cr, cc), '')
                lm = 3 if pm == 'TL' else 2 if pm == 'DL' else 1
                wm = 3 if pm == 'TW' else 2 if pm == 'DW' else 1
                empty_ahead_mults.append(lm)
                word_mult_ahead *= wm
                cross_sum += self.max_cross.get((cr, cc, direction), 0)
                placements_left -= 1
            else:
                if (cr, cc) not in self.blanks:
                    existing_ahead_value += TILE_PTS[self.board[cr][cc]]
            cr += dr; cc += dc

        k = len(empty_ahead_mults)
        if k == 0:
            # Can't place more; UB is just current main score + cross_total
            # + any bingo bonus already earned from prior placements.
            bingo = 40 if len(placements) >= 7 else 0
            return ((main_base + existing_ahead_value) * main_mult
                    + cross_total + bingo)

        # Greedy: pair top-k rack values (desc) with top-k letter multipliers (desc)
        rack_vals = sorted(
            (TILE_PTS[L] for L, n in rack_left.items() for _ in range(n)),
            reverse=True,
        )[:k]
        letter_mults_sorted = sorted(empty_ahead_mults, reverse=True)
        ub_letters = sum(rv * lm for rv, lm in zip(rack_vals, letter_mults_sorted))

        ub_main = (main_base + existing_ahead_value + ub_letters) * main_mult * word_mult_ahead
        ub_cross = cross_total + cross_sum
        ub_bingo = 40 if len(placements) + k >= 7 else 0
        return ub_main + ub_cross + ub_bingo

    def find_all_moves(self):
        """Find all valid moves. Returns sorted list.

        Uses branch-and-bound pruning when self.no_prune is False and
        self.top_n > 0, and enforces self.time_limit seconds (0 = unlimited)
        of wall-clock time. On timeout, returns partial results and sets
        self.timed_out = True.
        """
        self.moves = []
        self.top_heap = []
        self.timed_out = False
        rack_counter = Counter(self.rack)

        self.deadline = (time.monotonic() + self.time_limit) if self.time_limit > 0 else None

        if self.engine == 'trie':
            if self.trie is None:
                raise ValueError("engine='trie' requires a trie root to be set")
            self._precompute_cross_masks()
        elif self.engine == 'gaddag':
            if self.gaddag is None:
                raise ValueError("engine='gaddag' requires a gaddag root to be set")
            self._precompute_cross_masks()
            # Left-extent limits are anchor-dependent; compute below once
            # the anchor set is finalized.
        else:
            # Precompute max_cross for B&B bound (also cheap enough to keep even
            # under --no-prune; only ~11k dict lookups).
            self._precompute_max_cross()

        anchors = set()
        for r in range(15):
            for c in range(15):
                if self.board[r][c] != '.':
                    for ddr, ddc in [(-1,0),(1,0),(0,-1),(0,1)]:
                        nr, nc = r+ddr, c+ddc
                        if 0<=nr<15 and 0<=nc<15 and self.board[nr][nc] == '.':
                            anchors.add((nr, nc))

        if not anchors and self.board[7][7] == '.':
            anchors.add((7, 7))

        if self.engine == 'gaddag':
            self._precompute_left_limits(anchors)

        try:
            for direction in ['H', 'V']:
                dr = 0 if direction == 'H' else 1
                dc = 1 if direction == 'H' else 0

                for ar, ac in anchors:
                    if self.engine == 'gaddag':
                        # GADDAG walks both leftward (via SEP) and rightward
                        # from the anchor internally. No `before` loop needed.
                        self._build_gaddag(ar, ac, dr, dc, direction,
                                           rack_counter)
                        continue

                    max_before = 0
                    cr, cc = ar - dr, ac - dc
                    while (0<=cr<15 and 0<=cc<15 and self.board[cr][cc] == '.'
                           and (cr,cc) not in anchors and max_before < len(self.rack)-1):
                        max_before += 1
                        cr -= dr; cc -= dc

                    for before in range(max_before + 1):
                        sr = ar - before * dr
                        sc = ac - before * dc
                        # Pre-main-word value: existing tiles immediately before sr
                        # that extend the main word. Walk back through contiguous tiles.
                        prefix_base = 0
                        prefix_letters = []
                        pr, pc = sr - dr, sc - dc
                        while (0 <= pr < 15 and 0 <= pc < 15
                               and self.board[pr][pc] != '.'):
                            if (pr, pc) not in self.blanks:
                                prefix_base += TILE_PTS[self.board[pr][pc]]
                            prefix_letters.append(self.board[pr][pc])
                            pr -= dr; pc -= dc

                        if self.engine == 'trie':
                            # Seed trie walk by traversing the fixed left-prefix
                            # of existing tiles in forward order. If any arc is
                            # missing, the whole branch is dead (no dict word
                            # starts with this prefix).
                            node = self.trie
                            for L in reversed(prefix_letters):
                                node = node.get(L)
                                if node is None:
                                    break
                            if node is None:
                                continue
                            self._build_trie(sr, sc, dr, dc, direction,
                                             rack_counter, [],
                                             anchors, ar, ac, node)
                        else:
                            self._build(sr, sc, dr, dc, direction, rack_counter,
                                        [], anchors, ar, ac,
                                        prefix_base, 1, 0)
        except _TimeLimit:
            self.timed_out = True
            elapsed = time.monotonic() - (self.deadline - self.time_limit)
            print(f"WARNING: time limit reached at {elapsed:.1f}s -- "
                  f"returning {len(self.moves)} partial moves",
                  file=sys.stderr)

        # Deduplicate and sort. Same (word, positions, direction) with
        # different blank-letter choices collapses to the max-scoring variant.
        best = {}
        for score, word, placements, direction in self.moves:
            key = (word, frozenset((p[0], p[1]) for p in placements), direction)
            if key not in best or score > best[key][0]:
                best[key] = (score, word, placements, direction)
        unique = list(best.values())
        unique.sort(key=lambda x: -x[0])
        return unique

    def _build(self, r, c, dr, dc, direction, rack_left, placements,
               anchors, anchor_r, anchor_c,
               main_base, main_mult, cross_total):
        # Deadline check (cooperative)
        if self.deadline is not None and time.monotonic() >= self.deadline:
            raise _TimeLimit()

        if r < 0 or r >= 15 or c < 0 or c >= 15:
            self._try_complete(placements, direction, anchor_r, anchor_c)
            return

        # B&B prune: once top-N heap is saturated, skip branches whose UB <= threshold.
        if (not self.no_prune and self.top_n > 0
                and len(self.top_heap) >= self.top_n):
            ub = self._compute_ub(r, c, dr, dc, direction, rack_left, placements,
                                   main_base, main_mult, cross_total)
            if ub < self.top_heap[0]:
                return

        if self.board[r][c] != '.':
            # Walk through existing tile; add its value to main_base.
            v = 0 if (r, c) in self.blanks else TILE_PTS[self.board[r][c]]
            self._build(r+dr, c+dc, dr, dc, direction, rack_left,
                        placements, anchors, anchor_r, anchor_c,
                        main_base + v, main_mult, cross_total)
            return

        # Option: complete the play here (do not place at (r,c))
        self._try_complete(placements, direction, anchor_r, anchor_c)

        # Option: place a rack letter at (r,c) and recurse
        cdr, cdc = 1-dr, 1-dc
        pm = PREMIUM.get((r, c), '')
        letter_mult = 3 if pm == 'TL' else 2 if pm == 'DL' else 1
        word_mult_here = 3 if pm == 'TW' else 2 if pm == 'DW' else 1

        tried = set()
        for rack_letter in list(rack_left.keys()):
            if rack_left[rack_letter] <= 0 or rack_letter in tried:
                continue
            tried.add(rack_letter)

            # Blank: expand to each A-Z in frequency order (helps B&B converge).
            if rack_letter == '?':
                candidates = [(L, L.lower()) for L in BLANK_LETTER_ORDER]
            else:
                candidates = [(rack_letter, rack_letter)]

            rack_left[rack_letter] -= 1
            for board_letter, placement_letter in candidates:
                self.board[r][c] = board_letter
                cw, csr, csc = self.get_word_at(r, c, cdr, cdc)
                if len(cw) >= 2 and cw not in self.valid_words:
                    self.board[r][c] = '.'
                    continue

                is_blank = placement_letter.islower()
                letter_val = 0 if is_blank else TILE_PTS[board_letter]
                new_main_base = main_base + letter_val * letter_mult
                new_main_mult = main_mult * word_mult_here

                cross_score_here = 0
                if len(cw) >= 2:
                    cross_score_here = self._cross_score_for_placement(
                        r, c, cdr, cdc, csr, csc,
                        letter_val, letter_mult, word_mult_here)

                self.board[r][c] = '.'

                placements.append((r, c, placement_letter))
                self._build(r+dr, c+dc, dr, dc, direction, rack_left,
                            placements, anchors, anchor_r, anchor_c,
                            new_main_base, new_main_mult,
                            cross_total + cross_score_here)
                placements.pop()
            rack_left[rack_letter] += 1

    def _build_trie(self, r, c, dr, dc, direction, rack_left, placements,
                    anchors, anchor_r, anchor_c, trie_node):
        """Forward-trie-guided variant of _build.

        Walks the trie in lockstep with the main-word cells along (dr, dc).
        Every recursive call corresponds to a valid dictionary prefix,
        which is the main win over the naive _build. Cross-words are
        pruned via the 26-bit cross_masks precomputed once per solve.
        Scoring and final validation remain in verify_and_score (called
        by _try_complete) so this path never re-implements scoring.
        """
        # Deadline check (cooperative)
        if self.deadline is not None and time.monotonic() >= self.deadline:
            raise _TimeLimit()

        if r < 0 or r >= 15 or c < 0 or c >= 15:
            # Main word runs off the edge. Emit only if the trie node we
            # are sitting on is terminal (i.e., the letters placed so far
            # spell a valid word).
            if trie_node.get('$', False):
                self._try_complete(placements, direction, anchor_r, anchor_c)
            return

        if self.board[r][c] != '.':
            # Walk through existing tile; trie arc must match.
            L = self.board[r][c]
            child = trie_node.get(L)
            if child is None:
                return
            self._build_trie(r+dr, c+dc, dr, dc, direction, rack_left,
                             placements, anchors, anchor_r, anchor_c, child)
            return

        # Empty cell. Option 1: the main word naturally ends before this
        # cell (no placement here). Emit iff the current trie node is
        # terminal -- that means the letters placed so far form a valid
        # word and this empty cell provides the right-boundary.
        if trie_node.get('$', False):
            self._try_complete(placements, direction, anchor_r, anchor_c)

        # Option 2: place a rack tile at (r, c) and recurse. Iterate over
        # trie arcs (not all A-Z) -- each arc is a dictionary-valid next
        # letter. Skip any letter not allowed by the cross-check mask.
        cross_mask = self.cross_masks_h[r][c] if direction == 'H' else self.cross_masks_v[r][c]
        has_q = rack_left.get('?', 0) > 0

        for L, child in trie_node.items():
            if L == '$':
                continue
            bit = LETTER_BIT[L]
            if not (cross_mask & bit):
                continue

            if rack_left.get(L, 0) > 0:
                rack_left[L] -= 1
                placements.append((r, c, L))
                self._build_trie(r+dr, c+dc, dr, dc, direction, rack_left,
                                 placements, anchors, anchor_r, anchor_c,
                                 child)
                placements.pop()
                rack_left[L] += 1

            if has_q:
                rack_left['?'] -= 1
                placements.append((r, c, L.lower()))
                self._build_trie(r+dr, c+dc, dr, dc, direction, rack_left,
                                 placements, anchors, anchor_r, anchor_c,
                                 child)
                placements.pop()
                rack_left['?'] += 1

    def _build_gaddag(self, ar, ac, dr, dc, direction, rack_left):
        """Gordon GADDAG Gen/GoOn entry with Appel-Jacobson leftmost-anchor
        discipline. Anchor cell is assumed empty.

        The GADDAG is walked bidirectionally from the anchor:
          * Leftward (offset <= 0) consumes the reversed-prefix arcs.
          * A SEP arc switches to rightward (offset >= 1) for the suffix.

        Left-extent limit (self.left_limits[(ar, ac, direction)]) caps
        the number of tiles PLACED strictly to the left of the anchor
        (offset < 0). This makes every word have exactly one "home
        anchor" (the leftmost pre-move anchor in its placements), so
        cross-anchor duplicate generation is eliminated at the source.
        """
        left_limit = self.left_limits[(ar, ac, direction)]
        self._gen_left(ar, ac, dr, dc, direction, 0, self.gaddag,
                       rack_left, [], ar, ac, left_limit, 0)

    def _gen_left(self, ar, ac, dr, dc, direction, offset, node,
                  rack_left, placements, anchor_r, anchor_c,
                  left_limit, placed_left):
        if self.deadline is not None and time.monotonic() >= self.deadline:
            raise _TimeLimit()
        r = ar + offset * dr
        c = ac + offset * dc
        if not (0 <= r < 15 and 0 <= c < 15):
            return
        if self.board[r][c] != '.':
            # Walk through an existing tile. placed_left unchanged.
            L = self.board[r][c]
            child = node.get(L)
            if child is None:
                return
            self._go_on_left(ar, ac, dr, dc, direction, offset, child,
                             rack_left, placements, anchor_r, anchor_c,
                             left_limit, placed_left)
            return
        cross_mask = self.cross_masks_h[r][c] if direction == 'H' else self.cross_masks_v[r][c]
        has_q = rack_left.get('?', 0) > 0
        # At offset == 0 (anchor), placement is always allowed. At
        # offset < 0, only if placed_left < left_limit.
        can_place = (offset == 0) or (placed_left < left_limit)
        new_placed_left = placed_left if offset == 0 else placed_left + 1
        for L, child in node.items():
            if L == gaddag_mod.TERMINAL:
                continue
            if L == gaddag_mod.SEP:
                # No placement at this offset; switch to rightward walk.
                # Previous leftmost placement was at offset+1. Left walk
                # counter is frozen at the handoff.
                if placements:
                    self._gen_right(ar, ac, dr, dc, direction, 1, child,
                                    rack_left, placements,
                                    anchor_r, anchor_c, offset + 1)
                continue
            if not can_place:
                continue
            bit = LETTER_BIT[L]
            if not (cross_mask & bit):
                continue
            if rack_left.get(L, 0) > 0:
                rack_left[L] -= 1
                placements.append((r, c, L))
                self._go_on_left(ar, ac, dr, dc, direction, offset, child,
                                 rack_left, placements, anchor_r, anchor_c,
                                 left_limit, new_placed_left)
                placements.pop()
                rack_left[L] += 1
            if has_q:
                rack_left['?'] -= 1
                placements.append((r, c, L.lower()))
                self._go_on_left(ar, ac, dr, dc, direction, offset, child,
                                 rack_left, placements, anchor_r, anchor_c,
                                 left_limit, new_placed_left)
                placements.pop()
                rack_left['?'] += 1

    def _go_on_left(self, ar, ac, dr, dc, direction, offset, node,
                    rack_left, placements, anchor_r, anchor_c,
                    left_limit, placed_left):
        # Emit: terminal reached on a full-reverse variant. Rightmost
        # placement is at offset 0 (anchor); require both boundaries open.
        if node.get(gaddag_mod.TERMINAL, False):
            lr = ar + (offset - 1) * dr
            lc = ac + (offset - 1) * dc
            left_open = (not (0 <= lr < 15 and 0 <= lc < 15)
                         or self.board[lr][lc] == '.')
            rr = ar + dr
            rc = ac + dc
            right_open = (not (0 <= rr < 15 and 0 <= rc < 15)
                          or self.board[rr][rc] == '.')
            if left_open and right_open:
                self._try_complete(placements, direction,
                                   anchor_r, anchor_c)
        # Continue leftward. placed_left is preserved; the next _gen_left
        # will decide whether to increment based on what it does.
        self._gen_left(ar, ac, dr, dc, direction, offset - 1, node,
                       rack_left, placements, anchor_r, anchor_c,
                       left_limit, placed_left)
        # Or cross SEP here and walk rightward. Leftmost placement is
        # the current offset (we just placed/walked into it). Counter is
        # not passed to the right walk.
        sep_child = node.get(gaddag_mod.SEP)
        if sep_child is not None:
            self._gen_right(ar, ac, dr, dc, direction, 1, sep_child,
                            rack_left, placements,
                            anchor_r, anchor_c, offset)

    def _gen_right(self, ar, ac, dr, dc, direction, offset, node,
                   rack_left, placements, anchor_r, anchor_c, leftmost):
        if self.deadline is not None and time.monotonic() >= self.deadline:
            raise _TimeLimit()
        r = ar + offset * dr
        c = ac + offset * dc
        if not (0 <= r < 15 and 0 <= c < 15):
            return
        if self.board[r][c] != '.':
            L = self.board[r][c]
            child = node.get(L)
            if child is None:
                return
            self._go_on_right(ar, ac, dr, dc, direction, offset, child,
                              rack_left, placements,
                              anchor_r, anchor_c, leftmost)
            return
        cross_mask = self.cross_masks_h[r][c] if direction == 'H' else self.cross_masks_v[r][c]
        has_q = rack_left.get('?', 0) > 0
        for L, child in node.items():
            if L == gaddag_mod.TERMINAL or L == gaddag_mod.SEP:
                continue
            bit = LETTER_BIT[L]
            if not (cross_mask & bit):
                continue
            if rack_left.get(L, 0) > 0:
                rack_left[L] -= 1
                placements.append((r, c, L))
                self._go_on_right(ar, ac, dr, dc, direction, offset, child,
                                  rack_left, placements,
                                  anchor_r, anchor_c, leftmost)
                placements.pop()
                rack_left[L] += 1
            if has_q:
                rack_left['?'] -= 1
                placements.append((r, c, L.lower()))
                self._go_on_right(ar, ac, dr, dc, direction, offset, child,
                                  rack_left, placements,
                                  anchor_r, anchor_c, leftmost)
                placements.pop()
                rack_left['?'] += 1

    def _go_on_right(self, ar, ac, dr, dc, direction, offset, node,
                     rack_left, placements, anchor_r, anchor_c, leftmost):
        if node.get(gaddag_mod.TERMINAL, False):
            lr = ar + (leftmost - 1) * dr
            lc = ac + (leftmost - 1) * dc
            left_open = (not (0 <= lr < 15 and 0 <= lc < 15)
                         or self.board[lr][lc] == '.')
            rr = ar + (offset + 1) * dr
            rc = ac + (offset + 1) * dc
            right_open = (not (0 <= rr < 15 and 0 <= rc < 15)
                          or self.board[rr][rc] == '.')
            if left_open and right_open:
                self._try_complete(placements, direction,
                                   anchor_r, anchor_c)
        self._gen_right(ar, ac, dr, dc, direction, offset + 1, node,
                        rack_left, placements,
                        anchor_r, anchor_c, leftmost)

    def _try_complete(self, placements, direction, anchor_r, anchor_c):
        if not placements:
            return
        if not any(p[0]==anchor_r and p[1]==anchor_c for p in placements):
            return
        if self.engine in ('trie', 'gaddag'):
            score, main_word, cross_words = self._score_only(
                list(placements), direction)
            valid = score > 0
        else:
            valid, score, main_word, cross_words = self.verify_and_score(
                list(placements), direction)
        if valid and score > 0:
            self.moves.append((score, main_word, list(placements), direction))
            # Maintain top-N min-heap for B&B pruning threshold.
            if self.top_n > 0:
                if len(self.top_heap) < self.top_n:
                    heapq.heappush(self.top_heap, score)
                elif score > self.top_heap[0]:
                    heapq.heapreplace(self.top_heap, score)


# ============================================================
# Full-board ASCII rendering for moves
# ============================================================
def render_full_board_move(board, move, rank, blanks=None):
    """Render a move as a full 15x15 ASCII board with premium squares."""
    import io
    score, word, placements, direction = move
    b = copy.deepcopy(board)
    new_tiles = {}
    tiles_used = []
    for r, c, letter in placements:
        b[r][c] = letter.upper()
        new_tiles[(r,c)] = letter  # preserve lowercase for blanks
        tiles_used.append(letter)

    # Header
    premium_info = []
    for r, c, letter in placements:
        pm = PREMIUM.get((r,c), '')
        if pm:
            premium_info.append(f"{letter}@({r},{c})={PREMIUM_DISPLAY[pm]}")
    pm_str = "  " + ", ".join(premium_info) if premium_info else ""

    buf = io.StringIO()
    print(f"#{rank}: {word} -- {score} pts ({direction}){pm_str}", file=buf)
    print(f"    Tiles placed: {', '.join(tiles_used)}", file=buf)
    print_full_board(b, new_tiles, blanks, file=buf)
    return buf.getvalue()


def get_cross_words_for_move(board, solver, placements, direction):
    """Return the cross words formed by one move."""
    for r, c, letter in placements:
        board[r][c] = letter.upper()
    try:
        cross_dr = 1 if direction == 'H' else 0
        cross_dc = 1 if direction == 'V' else 0
        cross_words = []
        for r, c, _ in placements:
            word, _, _ = solver.get_word_at(r, c, cross_dr, cross_dc)
            if len(word) >= 2:
                cross_words.append(word)
        return sorted(set(cross_words))
    finally:
        for r, c, _ in placements:
            board[r][c] = '.'


def build_move_record(board, solver, rack, move):
    """Convert a solver move to the JSON schema used by moves_template.py."""
    score, word, placements, direction = move
    cross_words = get_cross_words_for_move(
        board, solver, placements, direction
    )
    if direction == 'H':
        direction_label = f"across, row {placements[0][0]}"
    else:
        direction_label = f"down, column {placements[0][1]}"

    leave = list(rack)
    premium_notes = []
    for r, c, letter in placements:
        rack_tile = '?' if letter.islower() else letter.upper()
        if rack_tile in leave:
            leave.remove(rack_tile)
        premium_type = PREMIUM.get((r, c))
        if premium_type:
            premium_notes.append(
                f"{letter.upper()} on {PREMIUM_DISPLAY[premium_type]}"
            )

    if premium_notes:
        note = f"Premiums: {', '.join(premium_notes)}. "
    else:
        note = "No premium square. "
    if len(placements) == 7:
        note += "Seven-tile play: 40-point bonus. "
    leave_text = ", ".join(
        "blank" if letter == '?' else letter for letter in leave
    )
    note += f"Rack leave: {leave_text or 'empty'}."

    return {
        "word": word,
        "pts": score,
        "dir": direction_label,
        "tiles": {
            f"{r},{c}": letter
            for r, c, letter in placements
        },
        "cross": ", ".join(cross_words) if cross_words else "-",
        "note": note,
    }


def write_moves_json(path, moves):
    """Write rendered move data to a UTF-8 JSON file."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump({"moves": moves}, f, indent=2)
        f.write("\n")
    print(f"Move JSON written to: {output_path}")


# ============================================================
# Main
# ============================================================
def main():
    parser = argparse.ArgumentParser(description='Word Game Board Solver')
    board_source = parser.add_mutually_exclusive_group(required=True)
    board_source.add_argument('--board', help='Path to board JSON file')
    board_source.add_argument('--board-text', help='Path to board text file')
    parser.add_argument('--rack', help="Rack letters; use '?' for each blank tile")
    parser.add_argument('--dict', help='Path to dictionary file')
    parser.add_argument('--top', type=int, default=10, help='Top N moves')
    parser.add_argument('--full-board', action='store_true',
                        help='Show full-board ASCII with premium squares')
    parser.add_argument('--full-board-count', type=int, default=3,
                        help='Number of full-board diagrams')
    parser.add_argument('--confirm-only', action='store_true',
                        help='Just print the board for confirmation, do not solve')
    parser.add_argument('--quiet', '-q', action='store_true',
                        help='Suppress board print and reduce output (use with HTML rendering)')
    parser.add_argument('--json-output',
                        help='Write top moves as renderer-compatible JSON')
    parser.add_argument('--time-limit', type=int, default=0, metavar='SECONDS',
                        help='Wall-clock cap on solve time (0 = unlimited, default). '
                             'On timeout, partial results are emitted with a stderr warning.')
    parser.add_argument('--no-prune', action='store_true',
                        help='Disable branch-and-bound pruning (debug / equivalence test). '
                             'Much slower but exhaustively explores every branch. '
                             'Naive engine only; ignored under --engine trie.')
    parser.add_argument('--engine', choices=['trie', 'gaddag', 'naive'], default='trie',
                        help='Move-generation engine. trie (default) uses a forward '
                             'dictionary trie to prune main-word prefixes early. '
                             'gaddag uses a bidirectional Gordon GADDAG, walking '
                             'both left and right of each anchor without an outer '
                             'before-loop. naive is the original cell-by-cell '
                             'search with B&B pruning; kept for correctness '
                             'equivalence testing.')
    # Legacy flags for backwards compatibility
    parser.add_argument('--ascii', action='store_true', help='(legacy) same as --full-board')
    parser.add_argument('--ascii-count', type=int, default=5, help='(legacy) same as --full-board-count')
    args = parser.parse_args()
    if args.top < 1:
        parser.error("--top must be at least 1")
    if args.time_limit < 0:
        parser.error("--time-limit must be non-negative")
    if args.ascii_count < 0:
        parser.error("--ascii-count must be non-negative")

    # Handle legacy flags
    if args.ascii and not args.full_board:
        args.full_board = True
        args.full_board_count = args.ascii_count
    if args.full_board_count < 0:
        parser.error("--full-board-count must be non-negative")

    try:
        if args.board:
            board, blanks = load_board_json(args.board)
        else:
            board, blanks = load_board_text(args.board_text)
    except (OSError, ValueError) as exc:
        parser.error(f"could not load board: {exc}")

    # Confirm-only mode: just print the board and exit
    if args.confirm_only:
        print("\nCurrent board (confirm with user before solving):")
        print_full_board(board, blanks=blanks)
        print()
        print(format_blank_inventory(board, blanks))
        return

    if not args.rack or not args.dict:
        parser.error("--rack and --dict are required unless --confirm-only is used")

    try:
        rack = validate_rack(args.rack)
    except ValueError as exc:
        parser.error(str(exc))
    if len(blanks) + rack.count('?') > 3:
        parser.error("The board and rack cannot contain more than three blanks total")
    print(f"Rack: {' '.join(rack)}")

    print("Loading dictionary...")
    try:
        valid_words, prefixes = load_dictionary(args.dict)
    except (OSError, ValueError) as exc:
        parser.error(f"could not load dictionary: {exc}")
    print(f"Dictionary: {len(valid_words)} words")

    trie_root = None
    gaddag_root = None
    if args.engine == 'trie':
        t_trie = time.time()
        print("Building dictionary trie ...")
        trie_root = wordtrie.build_trie(valid_words)
        print(f"Built trie in {time.time()-t_trie:.1f}s")
    elif args.engine == 'gaddag':
        t_g = time.time()
        print("Building dictionary GADDAG ...")
        gaddag_root = gaddag_mod.build_gaddag(valid_words)
        print(f"Built GADDAG in {time.time()-t_g:.1f}s")

    if not args.quiet:
        print("\nCurrent board:")
        print_board(board)

    print("\nFinding moves...")
    t0 = time.time()
    solver = BoardSolver(board, rack, valid_words, prefixes, blanks,
                        top_n=args.top, time_limit=args.time_limit,
                        no_prune=args.no_prune,
                        engine=args.engine, trie=trie_root,
                        gaddag=gaddag_root)
    all_moves = solver.find_all_moves()
    elapsed = time.time() - t0
    print(f"Found {len(all_moves)} valid moves in {elapsed:.1f}s (engine={args.engine})")

    if not all_moves:
        if args.json_output:
            write_moves_json(args.json_output, [])
        print("No valid moves found!")
        return

    top_moves = all_moves[:args.top]
    move_records = [
        build_move_record(board, solver, rack, move)
        for move in top_moves
    ]
    if args.json_output:
        write_moves_json(args.json_output, move_records)

    # Show top moves table
    print(f"\nTop {len(top_moves)} moves:")
    print(f"{'#':>3} {'Pts':>4} {'Word':<15} {'Dir':<4} {'Tiles placed':<30} {'Cross words'}")
    print("-"*90)
    paired_moves = zip(top_moves, move_records)
    for i, ((score, word, placements, d), record) in enumerate(paired_moves):
        tiles_str = ", ".join(f"{p[2]}@({p[0]},{p[1]})" for p in placements)
        print(f"{i+1:3d} {score:4d} {word:<15} {d:<4} "
              f"{tiles_str:<30} {record['cross']}")

    # Full-board ASCII diagrams
    if args.full_board:
        n = min(args.full_board_count, len(all_moves))
        print(f"\n{'='*60}")
        print(f"FULL BOARD DIAGRAMS FOR TOP {n} MOVES")
        print(f"{'='*60}")
        for i in range(n):
            print()
            print(render_full_board_move(board, all_moves[i], i+1, blanks))
            print()


if __name__ == '__main__':
    main()
