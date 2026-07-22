---
name: crossplay-solver-core
description: >-
  Solve NYT Crossplay board positions and answer Crossplay or NWL23 rack and
  word-list questions. Use whenever the user mentions NYT Crossplay or
  Crossplay, provides a Crossplay board screenshot, asks for a best play or a
  hint, or asks a word-game lookup involving rack letters or NWL23. Do not use
  for multiplayer cross-platform compatibility, unrelated crosswords, or
  Scrabble boards. Use for a general dictionary question only when the user
  explicitly invokes this skill. Handles board reconstruction, legal move
  generation, scoring, strategy notes, and visual results.
compatibility: >-
  Requires Python 3.8+, git, opencv-python, numpy, requests, filesystem access,
  and a user-accessible location for HTML and PNG outputs. Dictionary setup
  requires outbound HTTPS to github.com unless NWL23 source files are supplied.
---

# NYT Crossplay Solver

Find high-scoring legal moves from a board screenshot and rack, provide
non-spoiling hints, or answer Crossplay word-list questions.

## Resolve paths before running commands

Identify these absolute paths once:

- `<SKILL_DIR>`: this skill's installed `crossplay-solver-core` directory.
- `<WORK_DIR>`: a writable directory for `board.json`, `moves.json`,
  `dict.txt`, and dictionary caches.
- `<OUTPUT_DIR>`: a user-accessible directory for HTML and PNG artifacts.
- `<SCREENSHOT>`: the attached board screenshot.

Run bundled scripts directly from `<SKILL_DIR>/scripts`. Do not copy them into
the work directory; keeping imports together prevents mismatched script
versions.

## Bundled resources

- `scripts/setup_dict.py`: build the NWL23 dictionary.
- `scripts/grid_overlay.py`: locate the board and draw a numbered overlay.
- `scripts/solver.py`: validate board structure and generate scored moves.
- `scripts/moves_template.py`: render board confirmation and move HTML.
- `scripts/nwl23_ref.py`: curated strategic word lists and lookup helpers.

Load references only when needed:

- Read `references/game-rules.md` before manual score checks or strategic
  analysis.
- Read `references/dictionary.md` in Dictionary mode or for high-value word,
  hook, dump, and bingo guidance.
- Read `references/diagnostics.md` only when the default solver or overlay
  workflow fails or needs tuning.

## Choose a mode

### Dictionary mode

Choose this for a Crossplay or NWL23 lookup that does not require solving a
board, such as words ending in Z, four-letter Q words, or plays possible from
a rack.

If a screenshot is attached, inspect only the rack and use its letters as an
additional constraint. Set up `dict.txt`, read `references/dictionary.md`, and
filter the dictionary or curated lists with Python. Return a concise text list;
do not generate overlay, board, or move HTML.

### Hint mode

Choose this when the user asks for a hint, idea, direction, or area to explore
and supplies a screenshot. Follow the board workflow through the solve, but
return only subtle text hints:

- Point to a promising board area or premium lane.
- Describe a strategic pattern without revealing the exact word or cells.
- Mention an approximate score range when useful.

Generate the overlay and board-confirmation HTML, but not move HTML. The board
still needs user confirmation because hints based on a misread tile are not
useful.

### Full solver mode

Use this by default for a screenshot plus requests such as "solve", "best
move", or "what should I play?" Follow the complete workflow and render the
top moves.

## Board workflow

Use an incrementing round number `{N}` for every screenshot solved in the
conversation. This prevents later artifacts from overwriting earlier ones.

### 1. Set up the dictionary

Run once per conversation:

```bash
python "<SKILL_DIR>/scripts/setup_dict.py" --output "<WORK_DIR>/dict.txt"
```

Use `--full` only when the user asks for the complete 196K list. The default
playability list is smaller and better suited to normal move generation.
`setup_dict.py` reuses its source checkout; `solver.py` similarly caches a trie
beside `dict.txt`.

If dictionary setup fails, show the actual error and stop. Solving against a
substitute word list would change move legality without the user's knowledge.

### 2. Overlay and transcribe the board

```bash
python "<SKILL_DIR>/scripts/grid_overlay.py" "<SCREENSHOT>" --output "<OUTPUT_DIR>/overlay-{N}.png"
```

Inspect both the original screenshot and numbered overlay. Transcribe every
occupied cell into `<WORK_DIR>/board.json`:

```json
{
  "tiles": {
    "7,7": "A",
    "7,8": "R",
    "8,8": "k"
  }
}
```

Coordinates are zero-based `row,column`. Use lowercase only for a board tile
that was played as a blank; lowercase tells the solver that tile scores zero.

### 3. Check the reconstruction

Read `references/game-rules.md` and independently compute the most recently
reported play when the screenshot identifies its placement and score. A score
mismatch is strong evidence of a shifted column, missed tile, misread letter,
or blank.

Also inspect the solver's full-board rendering:

```bash
python "<SKILL_DIR>/scripts/solver.py" --board "<WORK_DIR>/board.json" --confirm-only
```

This command renders the transcription but does not perform dictionary
validation. Visually inspect contiguous letter sequences and correct obvious
nonsense against the screenshot.

### 4. Confirm the board with the user

Render a confirmation page through the bundled CLI:

```bash
python "<SKILL_DIR>/scripts/moves_template.py" board --board "<WORK_DIR>/board.json" --output "<OUTPUT_DIR>/board-{N}.html" --title "Board confirmation" --subtitle "Round {N}"
```

Present `board-{N}.html` and `overlay-{N}.png`, then wait for explicit
confirmation or corrections. This checkpoint is intentionally before the
solve because a single bad tile can invalidate every recommendation. Apply
corrections to `board.json` and regenerate the page before continuing.

### 5. Run the solver

```bash
python "<SKILL_DIR>/scripts/solver.py" --board "<WORK_DIR>/board.json" --rack "AILETEC" --dict "<WORK_DIR>/dict.txt" --top 5 --json-output "<WORK_DIR>/moves.json" --quiet
```

Represent each rack blank as `?`, for example `RA?OFHW`. The default trie
engine is the normal choice. Read `references/diagnostics.md` before selecting
another engine, disabling pruning, or changing time limits.

### 6. Present the result

In Hint mode, use the solver output internally and return only the subtle text
hints described above.

In Full Solver mode, `solver.py` writes the best five results directly to
`<WORK_DIR>/moves.json`. This preserves exact coordinates, blank-tile casing,
cross words, premiums, and rack leave without retyping the console table. The
file has this shape:

```json
{
  "moves": [
    {
      "word": "OXTER",
      "pts": 36,
      "dir": "across, row 11",
      "tiles": {
        "11,10": "O",
        "11,12": "T",
        "11,13": "E",
        "11,14": "R"
      },
      "cross": "-",
      "note": "R reaches 3W; balanced rack leave."
    }
  ]
}
```

Keep the best three to five entries. The solver supplies a factual note about
premiums and rack leave; expand it with any meaningful defensive tradeoff, but
do not rewrite coordinates or lowercase blank letters by hand.

Render the recommendations:

```bash
python "<SKILL_DIR>/scripts/moves_template.py" moves --board "<WORK_DIR>/board.json" --moves "<WORK_DIR>/moves.json" --output "<OUTPUT_DIR>/moves-{N}.html" --title "Crossplay recommendations" --subtitle "Round {N}"
```

Present `moves-{N}.html` with a concise text summary of the best move and any
important caveat.

## Report a problem

For a report to https://github.com/g-zhang/claude-crossplay/issues, include the
final non-empty `_Built from ..._` footer from this file when present, the
prompt and screenshot, exact error or incorrect result, and expected behavior.
If the footer is absent, identify the skill as a local or development install.
