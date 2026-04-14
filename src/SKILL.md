---
name: crossplay-solver
description: Solve NYT Crossplay board positions — find the highest-scoring legal moves given a board screenshot and a rack of tiles. Use this skill whenever the user mentions NYT Crossplay, Crossplay, or shares a screenshot of a Crossplay board and asks what to play, or references rack letters and wants move suggestions. Also use when the user asks dictionary questions like "words ending in Z" or "4 letter words with Q", or asks for hints/ideas on a Crossplay board. This skill handles board reconstruction from images, NWL23 dictionary setup, cross-word validation, premium square scoring, and visual HTML output of recommended plays.
---

# NYT Crossplay Board Solver

Finds the highest-scoring valid moves for an NYT Crossplay board, given the current board state and the player's tile rack.

## Overview

Four scripts:

1. **`scripts/setup_dict.py`** — clones NWL23 word lists from GitHub and builds a 145K-word tournament dictionary
2. **`scripts/grid_overlay.py`** — draws numbered grid lines on a screenshot for Claude to read tile positions manually
3. **`scripts/solver.py`** — solver engine: finds all legal moves, scores them
4. **`scripts/moves_template.py`** — shared HTML template for visual move boards and board confirmation. Supports light/dark mode. Exports `generate_board_confirm_html()` and `generate_moves_html()`.

## Modes

This skill operates in three modes. Detect the mode from the user's prompt before starting:

### 1. Dictionary Mode

**Trigger:** User invokes via `/` slash command and asks a dictionary lookup question — e.g. "is there a word that ends with Z", "4 letter words that begin with Q", "words with double L", "valid 2-letter words with X". No board solving is needed.

**If a screenshot is attached:** Only examine the tile rack to extract available letters, then constrain the dictionary search to those letters.

**Workflow:**
1. Set up dictionary (Step 1 from main workflow, if not already done)
2. Search `dict.txt` using grep/Python to answer the query (filter by length, pattern, available letters, etc.)
3. Also cross-reference `nwl23_ref.py` lists (TWO_LETTER, SHORT_J/Q/X/Z, etc.) when relevant
4. Respond with a text list of matching words — no board HTML, no overlay, no solver

### 2. Hint Mode

**Trigger:** User says "give me a hint", "give me ideas", "any suggestions", "where should I look", or similar hint/idea language, and attaches a screenshot.

**Workflow:**
1. Run the full solver pipeline (Steps 1–5) internally
2. **Do NOT output any HTML moves files.** Instead, respond with text-only subtle hints:
   - Point toward promising areas of the board (e.g. "there's an opening near the bottom-right triple word")
   - Mention strategic ideas (e.g. "your rack has good bingo potential", "look for hooks on existing short words")
   - Hint at letter combinations without giving away the exact word (e.g. "your high-value tile could pair well with what's in row 8")
   - Mention approximate point ranges ("there's a 30+ point play available")
3. Board confirmation (Step 4) is still required before running the solver
4. Output `board-{N}.html` and `overlay-{N}.png` as usual for board confirmation, but skip `moves-{N}.html`

### 3. Full Solver Mode (default)

**Trigger:** Screenshot provided with no hint language, or explicit "solve", "what should I play", "best move", etc. This is the default when neither Dictionary nor Hint mode applies.

**Workflow:** Follow the full pipeline below (Steps 1–6).

---

## Full Solver Workflow

### Step 1: Set up dictionary (once per session)

```bash
cd /home/claude
cp -r <SKILL_DIR>/scripts .
python scripts/setup_dict.py --output dict.txt
```

Second run in same session is instant (repo cached). Use `--full` flag for the complete 196K word list.



### Step 2: Read the board

```bash
python scripts/grid_overlay.py /mnt/user-data/uploads/<screenshot>.png -o /home/claude/overlay-{N}.png
```

View the overlay image and manually read each green-highlighted cell's letter using the numbered grid lines. Build board.json from what you see.

### Step 3: Verify and fix the board

**Score verification (REQUIRED):** Check the last-played word's score against what the screenshot reports. For example, if the screenshot says "Enoch played GAIN for 24 points", compute GAIN's score from the board placement. If it doesn't match, fix the board JSON.

**Fix errors:** Replace any misreads in board.json by viewing the original screenshot.

**Cross-word validation:** Run the solver in confirm-only mode. Nonsense cross-words indicate errors.

### Step 4: Confirm the board with the user (REQUIRED)

**Before solving**, generate an HTML board confirmation and present it to the user:

```python
import json, sys
sys.path.insert(0, 'scripts')
from moves_template import generate_board_confirm_html

with open('board.json') as f:
    board = json.load(f).get("tiles", json.load(open('board.json')))

PREMIUM = {}  # ... (copy premium dict from solver constants)

generate_board_confirm_html(
    board=board, premium=PREMIUM,
    output_path="/mnt/user-data/outputs/board-{N}.html",
    title="Board Confirmation — vs Opponent",
    subtitle="You: X · Opponent: Y · Last play: WORD for N pts"
)
```

Present both the HTML file (`board-{N}.html`) and the grid overlay PNG (`overlay-{N}.png`) to the user and **wait for confirmation** before solving. This catches tile detection errors (false positives from premium squares, missed tiles, misread letters) before they waste a solve cycle.

### Step 5: Run the solver

```bash
python scripts/solver.py \
    --board board.json \
    --rack AILETEC \
    --dict dict.txt \
    --top 10 \
    -q
```

**Flags:**
- `--top N` — top N moves in summary table (default 10)
- `-q` / `--quiet` — suppress board print, reduce output tokens (recommended when generating HTML visuals)
- `--full-board` — full-board ASCII diagrams (only use for debugging, not needed with HTML output)
- `--full-board-count N` — how many diagrams (default 3)
- `--confirm-only` — just print board for confirmation, don't solve

### Step 6: Present results visually

**Always show the top 3-5 moves as visual board diagrams** using the `moves_template.py` module. This generates themed HTML that works in both light and dark mode.

```python
from moves_template import generate_moves_html

moves = [
    {"word": "OXTER", "pts": 36, "dir": "across row 11",
     "tiles": {"11,10": "O", "11,12": "T", "11,13": "E", "11,14": "R"},
     "cross": "—",
     "note": "R on 3W triples the word. Rack leave: [blank], I, I."},
    # ... more moves
]

generate_moves_html(
    title="Round N — description",
    subtitle="You: X · Opponent: Y · Rack: ... · N tiles left",
    board=BOARD_DICT, premium=PREMIUM_DICT, moves=moves,
    output_path="/mnt/user-data/outputs/moves-{N}.html"
)
```

**Round counter:** Replace `{N}` with an incrementing integer (1, 2, 3, …) for each solve in the conversation. This applies to all outputs: `board-{N}.html`, `overlay-{N}.png`, and `moves-{N}.html`. This preserves every output as a separate artifact so earlier results are not overwritten.

Each move diagram shows:
- Existing tiles in blue, **new tiles in orange** with inset border
- Premium squares with colors that adapt to light/dark mode
- Word, score, cross-words, and strategic notes beneath each board

**Strategic notes to include per move:**
- Premium squares hit (e.g. "X on 2W")
- Rack leave quality (vowel/consonant balance, dangerous letters kept)
- Defensive considerations (opening triple lanes, blocking)

## NYT Crossplay Tile Values

| Pts | Letters |
|-----|---------|
| 1 | A, E, I, N, O, R, S, T |
| 2 | D, L, U |
| 3 | B, C, H, M, P |
| 4 | F, G, Y |
| 5 | W |
| 6 | K, V |
| 8 | J, X |
| 10 | Q, Z |

## NYT Crossplay Premium Layout (56 squares, fully symmetric)

| Type | Positions |
|------|-----------|
| 3W (x8) | (0,3) (0,11) (3,0) (3,14) (11,0) (11,14) (14,3) (14,11) |
| 2W (x8) | (1,1) (1,13) (3,7) (7,3) (7,11) (11,7) (13,1) (13,13) |
| 3L (x20) | (0,0) (0,14) (1,6) (1,8) (4,5) (4,9) (5,4) (5,10) (6,1) (6,13) (8,1) (8,13) (9,4) (9,10) (10,5) (10,9) (13,6) (13,8) (14,0) (14,14) |
| 2L (x20) | (0,7) (2,4) (2,10) (3,3) (3,11) (4,2) (4,12) (5,7) (7,0) (7,5) (7,9) (7,14) (9,7) (10,2) (10,12) (11,3) (11,11) (12,4) (12,10) (14,7) |

## Scoring Rules

- **Letter premiums (2L, 3L)**: multiply only the single letter on that square.
- **Word premiums (2W, 3W)**: multiply the entire word. Multiple word premiums stack.
- Premiums only apply to NEW tiles, not existing board tiles.
- Cross-words get premiums from newly placed tiles too.
- All 7 tiles in one play = **40-point bonus** (Crossplay).
- Center (7,7) has **no premium**.

## Endgame Rules (Crossplay)

- The game ends when the tile bag is empty and each player has had one more turn.
- There is **no penalty** for remaining tiles at end of game. Do not factor rack-leave point deductions into endgame strategy.
- Strategic implication: near endgame, focus purely on maximizing points scored rather than emptying your rack.

## Grid Overlay Technical Details

The `grid_overlay.py` script uses a two-phase board detection:

1. **Edge-based crop**: Canny edges -> row/col projection -> find board extent. Handles the coarse crop.
2. **Dual-anchor premium calibration**: Scans left, right, and top edges for premium square clusters (saturation > 20 in HSV). The first and last clusters on the left/right edges correspond to the centers of rows 0 and 14 — their distance gives the exact cell size (span / 14). Similarly, horizontal clusters in the top row pin column positions. This anchors both the start AND end of the grid, preventing cumulative drift that occurs when only the top edge is used.

The script also adds left padding to the output image when the board is near the left edge, ensuring row labels are always visible.

Blue tile detection uses HSV filtering tuned for Crossplay's tile color:
- H: 85-130, S: >=55, V: >=80
- Cell classified as tile if >42% of pixels match
- This cleanly separates tiles (ratio 0.42-0.90) from premium squares (ratio 0.30-0.39)

## Troubleshooting

- **Score mismatch**: Verify board column alignment first. Check for blank tiles. Verify tile values match the game.
- **No moves found**: Check board reconstruction. Verify existing words are in dict.txt.
- **Grid overlay misaligned**: The dual-anchor calibration requires at least 2 premium clusters on both left and right edges. If premium squares are covered by tiles, the fallback uses single-edge detection. You can also tune the HSV thresholds in `grid_overlay.py`.
- **False positive tiles**: If premium squares are detected as tiles, increase the ratio threshold above 0.42. If tiles are missed, decrease it.

## NWL23 Reference (scripts/nwl23_ref.py)

Contains extracted word lists from the official NWL23 Cheat Sheet. Import and use for:

```python
from nwl23_ref import (
    TWO_LETTER,           # Set of 107 valid 2-letter words
    SHORT_J, SHORT_Q,     # Short high-value words (2-4 letters)
    SHORT_X, SHORT_Z,
    BINGO_STEMS,          # TISANE/SATIRE/RETINA letter sets
    HI_PROB_7,            # 156 high-probability 7-letter bingos
    VOWEL_DUMPS,          # Words to dump excess vowels
    I_DUMPS, U_DUMPS,     # Duplicate-letter dumps
    is_valid_2letter,     # Quick 2-letter validation
    validate_crosswords,  # Check cross-word list
    check_bingo_potential,# Check rack for bingo stems
    get_premium_words,    # Short J/Q/X/Z words for premium targeting
    find_dump_words,      # Find dump plays from rack
)
```

**Integration with solver output:**
- After running the solver, validate all 2-letter cross-words against `TWO_LETTER`
- Flag any cross-word not in the set as INVALID — the play will be rejected
- Check rack for bingo potential before solving — if TISANE/SATIRE/RETINA overlap ≥5, prioritize 7-tile plays
- When holding J/Q/X/Z, cross-reference `SHORT_X` etc. for premium-square targeting ideas
