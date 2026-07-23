# claude-crossplay
A Claude AI [skill](core/SKILL.md) for solving [NYT Crossplay](https://www.nytimes.com/games/crossplay) board positions — finds the highest-scoring legal moves given a board screenshot and rack of tiles.

---

## What It Does

Given a screenshot of a Crossplay board and your current tile rack, this skill:

1. Detects tile positions on the board using HSV color filtering and dual-anchor grid calibration
2. Audits every source score corner against the transcribed letter and blank status
3. Builds a tournament-grade dictionary from the **NWL23** word list (~145K words)
4. Finds all legal moves and scores them correctly (letter/word multipliers, cross-words, 40-pt bingo bonus)
5. Outputs the top moves as standalone HTML visualizations with strategic notes

## Scripts

| Script | Purpose |
|--------|---------|
| [`fetch_core.py`](src/scripts/fetch_core.py) | Creates a fresh sparse checkout for the auto-updating bootstrap skill |
| [`setup_dict.py`](core/scripts/setup_dict.py) | Fetches a pinned NWL23 source revision and builds `dict.txt` |
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
  that creates a fresh sparse checkout once per conversation and always runs
  the latest scripts from `main`. Requires network access inside Claude's
  sandbox.
- **`crossplay-solver-core`** *(bundled scripts)* — packages the complete
  workflow directly. Dictionary setup still needs GitHub access unless
  compatible NWL23 source files are supplied.

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
3. Verify the board by checking the last play's score when it is available
4. Show you the tile audit and an HTML board confirmation before solving
5. Run the solver and present the top moves visually

## Running locally
### Requirements
- Python 3.8+
- `opencv-python`, `numpy`

```bash
pip install opencv-python numpy
```

Or, with [uv](https://docs.astral.sh/uv/):

```bash
uv sync          # creates .venv and installs deps from pyproject.toml
```
### Example
```text
# Run these commands from the repository root.

# 1. Build the dictionary.
python core/scripts/setup_dict.py --output dict.txt

# 2. Generate a numbered overlay, then transcribe board.json.
python core/scripts/grid_overlay.py screenshot.png --output overlay.png

# 3. Audit every transcribed tile and score corner.
python core/scripts/grid_overlay.py screenshot.png --output overlay.png --board-json board.json --tile-audit tile-audit.png

# 4. Inspect the parsed board and explicit blank inventory.
python core/scripts/solver.py --board board.json --confirm-only

# 5. Render board confirmation and verify it before solving.
python core/scripts/moves_template.py board --board board.json --output board.html --title "Board confirmation"

# 6. After confirmation, generate renderer-compatible move data.
python core/scripts/solver.py --board board.json --rack AILETEC --dict dict.txt --top 5 --json-output moves.json --quiet

# 7. Render the recommendations.
python core/scripts/moves_template.py moves --board board.json --moves moves.json --output moves.html --title "Crossplay recommendations"
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

```text
# Bootstrap (auto-updating) skill.
git archive --format=zip --prefix=crossplay-solver/ --output=crossplay-solver.skill HEAD:src

# Core (bundled) skill.
git archive --format=zip --prefix=crossplay-solver-core/ --output=crossplay-solver-core.skill HEAD:core
```

These commands package only tracked files from the current commit, preventing
local caches and generated artifacts from leaking into either archive.

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
