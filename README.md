# claude-crossplay
A Claude AI [skill](core/SKILL.md) for solving [NYT Crossplay](https://www.nytimes.com/games/crossplay) board positions — finds the highest-scoring legal moves given a board screenshot and rack of tiles.

> **Note:** This code was written by [Claude](https://claude.ai) (Anthropic's AI assistant) guided by user prompts.

---

## What It Does

Given a screenshot of a Crossplay board and your current tile rack, this skill:

1. Detects tile positions on the board using HSV color filtering and dual-anchor grid calibration
2. Builds a tournament-grade dictionary from the **NWL23** word list (~145K words)
3. Finds all legal moves and scores them correctly (letter/word multipliers, cross-words, 40-pt bingo bonus)
4. Outputs the top moves as interactive HTML visualizations with strategic notes

## Scripts

| Script | Purpose |
|--------|---------|
| [`setup_dict.py`](core/scripts/setup_dict.py) | Clones NWL23 word lists and builds `dict.txt` |
| [`grid_overlay.py`](core/scripts/grid_overlay.py) | Draws a numbered grid and a board-aware tile audit with enlarged score corners |
| [`solver.py`](core/scripts/solver.py) | Core solver engine — finds and scores all legal moves |
| [`moves_template.py`](core/scripts/moves_template.py) | Generates HTML board confirmations and move visualizations through a reusable CLI |
| [`nwl23_ref.py`](core/scripts/nwl23_ref.py) | NWL23 reference data: 2-letter words, bingo stems, high-value short words |

Detailed game rules, dictionary guidance, and troubleshooting live under
[`core/references/`](core/references/) so the main skill loads them only when
needed.

## Installation

Two distributions are available — install **one**:

- **`crossplay-solver`** *(auto-updating scripts)* — a thin bootstrap skill
  that clones this repo on first use and always runs the latest scripts
  from `main`. Requires network access inside Claude's sandbox.
- **`crossplay-solver-core`** *(offline scripts)* — the classic packaged
  skill with scripts bundled directly. The scripts themselves need no
  network, though `setup_dict.py` still fetches NWL23 from GitHub at
  runtime for either distribution.

1. Go to the [latest release](https://github.com/g-zhang/claude-crossplay/releases/latest) and download either `crossplay-solver.skill` or `crossplay-solver-core.skill`
2. In Claude Desktop, open **Settings → Skills**
3. Click **Add Skill** and select the downloaded `.skill` file
4. The skill is now available in your Claude conversations

## How to Use

This skill is designed to be invoked through a Claude conversation. Drop a Crossplay screenshot into the chat and ask Claude to solve it, or invoke it using `/crossplay-solver`. Then simply let Claude work and present the results.
Claude in the background will:

1. Run `grid_overlay.py` on your screenshot to number the cells
2. Read tile positions manually, then audit each source score corner against
   the JSON letter and blank status
3. Verify the board by checking the last play's score
4. Show you the tile audit and an HTML board confirmation before solving
5. Run the solver and present the top moves visually

## Running locally
### Requirements
- Python 3.8+
- `opencv-python`, `numpy`, `requests`

```bash
pip install opencv-python numpy requests
```

Or, with [uv](https://docs.astral.sh/uv/):

```bash
uv sync          # creates .venv and installs deps from pyproject.toml
```
### Example
```bash
# (from the repo root; all scripts live in core/scripts/)

# 1. Build the dictionary (once per session)
python core/scripts/setup_dict.py --output dict.txt

# 2. Generate a grid overlay for reading tile positions
python core/scripts/grid_overlay.py screenshot.png -o overlay.png

# 3. Transcribe board.json, then audit every score corner and blank marker
python core/scripts/grid_overlay.py screenshot.png \
    -o overlay.png \
    --board-json board.json \
    --tile-audit tile-audit.png

# 4. Run the solver
python core/scripts/solver.py \
    --board board.json \
    --rack AILETEC \
    --dict dict.txt \
    --top 10 \
    -q
```

### `board.json` format

```json
{
  "tiles": {
    "7,7": "A",
    "7,8": "R",
    "7,9": "T"
  }
}
```

Keys are `"row,col"` (0-indexed, 0 = top-left). Use lowercase for a tile
played as a blank; for example, `"8,8": "k"` represents a K worth zero points.

### Package skill

A `.skill` file is a ZIP archive whose root contains the skill folder. The folder name should match the `name` field in `SKILL.md`.

```bash
# Bootstrap (auto-updating) skill — zips src/
cp -r src crossplay-solver
zip -r crossplay-solver.skill crossplay-solver/
rm -rf crossplay-solver

# Core (offline) skill — zips core/
cp -r core crossplay-solver-core
zip -r crossplay-solver-core.skill crossplay-solver-core/
rm -rf crossplay-solver-core
```

This produces `crossplay-solver.skill` and `crossplay-solver-core.skill` in the project root with the correct structure:

```
crossplay-solver.skill
└── crossplay-solver/
    └── SKILL.md          # bootstrap: sparse-clones the repo, delegates to core

crossplay-solver-core.skill
└── crossplay-solver-core/
    ├── SKILL.md
    ├── references/
    └── scripts/
```

Install via **Settings → Skills → Add Skill** in Claude Desktop.
