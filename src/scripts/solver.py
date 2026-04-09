#!/usr/bin/env python3
"""
Word Game Board Solver (NYT Crossplay / Words With Friends)

Usage:
    python wwf_solver.py --board board.json --rack AILETEC --dict dict.txt [--top 20] [--full-board]
    python wwf_solver.py --board board.json --dict dict.txt --rack X --confirm-only

board.json format: {"row,col": "LETTER", ...}
  Use lowercase for blank tiles (0 pts): {"7,8": "k"}

Or pass a 15-line text board via --board-text board.txt
"""
import json
import sys
import argparse
import time
import copy
from collections import Counter
from pathlib import Path

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

# ============================================================
# NYT Crossplay Premium Squares (from empty board image analysis)
# 56 total: 8×3W, 8×2W, 20×3L, 20×2L — fully symmetric
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


def load_dictionary(dict_path):
    """Load dictionary and build prefix set."""
    with open(dict_path) as f:
        words = set(line.strip().upper() for line in f if line.strip())
    prefixes = set()
    for w in words:
        for i in range(1, len(w)+1):
            prefixes.add(w[:i])
    return words, prefixes


def load_board_json(path):
    """Load board from JSON format. Lowercase letters = blank tiles (0 pts)."""
    board = [['.']*15 for _ in range(15)]
    blanks = set()
    with open(path) as f:
        data = json.load(f)
    for key, letter in data.get("tiles", data).items():
        parts = key.split(',')
        r, c = int(parts[0].strip()), int(parts[1].strip())
        if letter.islower():
            blanks.add((r, c))
        board[r][c] = letter.upper()
    return board, blanks


def load_board_text(path):
    """Load board from 15-line text file (. = empty). Lowercase = blank."""
    board = [['.']*15 for _ in range(15)]
    blanks = set()
    with open(path) as f:
        lines = [l.rstrip('\n') for l in f.readlines()]
    for r, line in enumerate(lines[:15]):
        for c, ch in enumerate(line[:15]):
            if ch != '.' and ch.isalpha():
                if ch.islower():
                    blanks.add((r, c))
                board[r][c] = ch.upper()
    return board, blanks


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


# ============================================================
# Core solver
# ============================================================
class WWFSolver:
    def __init__(self, board, rack, valid_words, prefixes, blanks=None):
        self.board = board
        self.rack = rack
        self.valid_words = valid_words
        self.prefixes = prefixes
        self.blanks = blanks or set()
        self.moves = []

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
        """Verify a move and calculate its score."""
        if not placements:
            return False, 0, '', []

        dr = 0 if direction == 'H' else 1
        dc = 1 if direction == 'H' else 0
        cdr, cdc = 1-dr, 1-dc

        # Temporarily place tiles
        for r, c, letter in placements:
            self.board[r][c] = letter

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
                pts = 0 if (cr, cc) in self.blanks else TILE_PTS.get(ch, 0)
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
                    pts = 0 if (cr, cc) in self.blanks else TILE_PTS.get(ch, 0)
                    if (cr, cc) in placement_set:
                        pm = PREMIUM.get((cr, cc), '')
                        if pm == 'DL': pts *= 2
                        elif pm == 'TL': pts *= 3
                        elif pm == 'DW': cw_mult *= 2
                        elif pm == 'TW': cw_mult *= 3
                    cw_score += pts
                    cr += cdr; cc += cdc
                score += cw_score * cw_mult

            # 7-tile bonus (40 for Crossplay, 35 for WWF)
            if len(placements) == 7:
                score += 40

        # Remove temporary tiles
        for r, c, letter in placements:
            self.board[r][c] = '.'

        return valid, score, main_word, cross_words

    def find_all_moves(self):
        """Find all valid moves. Returns sorted list."""
        self.moves = []
        rack_counter = Counter(self.rack)

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

        for direction in ['H', 'V']:
            dr = 0 if direction == 'H' else 1
            dc = 1 if direction == 'H' else 0

            for ar, ac in anchors:
                max_before = 0
                cr, cc = ar - dr, ac - dc
                while (0<=cr<15 and 0<=cc<15 and self.board[cr][cc] == '.'
                       and (cr,cc) not in anchors and max_before < len(self.rack)-1):
                    max_before += 1
                    cr -= dr; cc -= dc

                for before in range(max_before + 1):
                    sr = ar - before * dr
                    sc = ac - before * dc
                    self._build(sr, sc, dr, dc, direction, rack_counter,
                                [], anchors, ar, ac)

        # Deduplicate and sort
        seen = set()
        unique = []
        for score, word, placements, direction in self.moves:
            key = (word, tuple(sorted((p[0],p[1]) for p in placements)), direction)
            if key not in seen:
                seen.add(key)
                unique.append((score, word, placements, direction))
        unique.sort(key=lambda x: -x[0])
        return unique

    def _build(self, r, c, dr, dc, direction, rack_left, placements,
               anchors, anchor_r, anchor_c):
        if r < 0 or r >= 15 or c < 0 or c >= 15:
            self._try_complete(placements, direction, anchor_r, anchor_c)
            return

        if self.board[r][c] != '.':
            self._build(r+dr, c+dc, dr, dc, direction, rack_left,
                        placements, anchors, anchor_r, anchor_c)
            return

        self._try_complete(placements, direction, anchor_r, anchor_c)

        cdr, cdc = 1-dr, 1-dc
        tried = set()
        for letter in list(rack_left.keys()):
            if rack_left[letter] > 0 and letter not in tried:
                tried.add(letter)
                self.board[r][c] = letter
                cw, _, _ = self.get_word_at(r, c, cdr, cdc)
                self.board[r][c] = '.'
                if len(cw) >= 2 and cw not in self.valid_words:
                    continue

                rack_left[letter] -= 1
                placements.append((r, c, letter))
                self._build(r+dr, c+dc, dr, dc, direction, rack_left,
                            placements, anchors, anchor_r, anchor_c)
                placements.pop()
                rack_left[letter] += 1

    def _try_complete(self, placements, direction, anchor_r, anchor_c):
        if not placements:
            return
        if not any(p[0]==anchor_r and p[1]==anchor_c for p in placements):
            return
        valid, score, main_word, cross_words = self.verify_and_score(
            list(placements), direction)
        if valid and score > 0:
            self.moves.append((score, main_word, list(placements), direction))


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
        b[r][c] = letter
        new_tiles[(r,c)] = letter
        tiles_used.append(letter)

    # Header
    premium_info = []
    for r, c, letter in placements:
        pm = PREMIUM.get((r,c), '')
        if pm:
            premium_info.append(f"{letter}@({r},{c})={PREMIUM_DISPLAY[pm]}")
    pm_str = "  " + ", ".join(premium_info) if premium_info else ""

    buf = io.StringIO()
    print(f"#{rank}: {word} — {score} pts ({direction}){pm_str}", file=buf)
    print(f"    Tiles placed: {', '.join(tiles_used)}", file=buf)
    print_full_board(b, new_tiles, blanks, file=buf)
    return buf.getvalue()


# ============================================================
# Main
# ============================================================
def main():
    parser = argparse.ArgumentParser(description='Word Game Board Solver')
    parser.add_argument('--board', help='Path to board JSON file')
    parser.add_argument('--board-text', help='Path to board text file')
    parser.add_argument('--rack', required=True, help='Rack letters')
    parser.add_argument('--dict', required=True, help='Path to dictionary file')
    parser.add_argument('--top', type=int, default=10, help='Top N moves')
    parser.add_argument('--full-board', action='store_true',
                        help='Show full-board ASCII with premium squares')
    parser.add_argument('--full-board-count', type=int, default=3,
                        help='Number of full-board diagrams')
    parser.add_argument('--confirm-only', action='store_true',
                        help='Just print the board for confirmation, do not solve')
    parser.add_argument('--quiet', '-q', action='store_true',
                        help='Suppress board print and reduce output (use with HTML rendering)')
    # Legacy flags for backwards compatibility
    parser.add_argument('--ascii', action='store_true', help='(legacy) same as --full-board')
    parser.add_argument('--ascii-count', type=int, default=5, help='(legacy) same as --full-board-count')
    args = parser.parse_args()

    # Handle legacy flags
    if args.ascii and not args.full_board:
        args.full_board = True
        args.full_board_count = args.ascii_count

    if args.board:
        board, blanks = load_board_json(args.board)
    elif args.board_text:
        board, blanks = load_board_text(args.board_text)
    else:
        print("ERROR: Provide --board (JSON) or --board-text (text file)", file=sys.stderr)
        sys.exit(1)

    # Confirm-only mode: just print the board and exit
    if args.confirm_only:
        print("\nCurrent board (confirm with user before solving):")
        print_full_board(board, blanks=blanks)
        return

    rack = list(args.rack.upper())
    print(f"Rack: {' '.join(rack)}")

    print("Loading dictionary...")
    valid_words, prefixes = load_dictionary(args.dict)
    print(f"Dictionary: {len(valid_words)} words")

    if not args.quiet:
        print("\nCurrent board:")
        print_board(board)

    print("\nFinding moves...")
    t0 = time.time()
    solver = WWFSolver(board, rack, valid_words, prefixes, blanks)
    all_moves = solver.find_all_moves()
    elapsed = time.time() - t0
    print(f"Found {len(all_moves)} valid moves in {elapsed:.1f}s")

    if not all_moves:
        print("No valid moves found!")
        return

    # Show top moves table
    print(f"\nTop {min(args.top, len(all_moves))} moves:")
    print(f"{'#':>3} {'Pts':>4} {'Word':<15} {'Dir':<4} {'Tiles placed':<30} {'Cross words'}")
    print("-"*90)
    for i, (score, word, placements, d) in enumerate(all_moves[:args.top]):
        tiles_str = ", ".join(f"{p[2]}@({p[0]},{p[1]})" for p in placements)
        # Get cross words
        for p in placements:
            board[p[0]][p[1]] = p[2]
        cdr_val = 1 if d == 'H' else 0
        cdc_val = 1 if d == 'V' else 0
        cw_list = []
        for p in placements:
            cw, _, _ = solver.get_word_at(p[0], p[1], cdr_val, cdc_val)
            if len(cw) >= 2:
                cw_list.append(cw)
        for p in placements:
            board[p[0]][p[1]] = '.'
        cw_str = ", ".join(sorted(set(cw_list))) if cw_list else "-"
        print(f"{i+1:3d} {score:4d} {word:<15} {d:<4} {tiles_str:<30} {cw_str}")

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
