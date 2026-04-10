# claude-crossplay
A Claude AI [skill](src/SKILL.md) for solving [NYT Crossplay](https://www.nytimes.com/games/crossplay) board positions — finds the highest-scoring legal moves given a board screenshot and rack of tiles.

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
| [`setup_dict.py`](src/scripts/setup_dict.py) | Clones NWL23 word lists and builds `dict.txt` |
| [`grid_overlay.py`](src/scripts/grid_overlay.py) | Draws a numbered grid on a board screenshot for manual tile reading |
| [`solver.py`](src/scripts/solver.py) | Core solver engine — finds and scores all legal moves |
| [`moves_template.py`](src/scripts/moves_template.py) | Generates HTML board visualizations (light/dark mode) |
| [`nwl23_ref.py`](src/scripts/nwl23_ref.py) | NWL23 reference data: 2-letter words, bingo stems, high-value short words |

## Installation

1. Go to the [latest release](https://github.com/g-zhang/claude-crossplay/releases/latest) and download `crossplay-solver.skill`
2. In Claude Desktop, open **Settings → Skills**
3. Click **Add Skill** and select the downloaded `crossplay-solver.skill` file
4. The skill is now available in your Claude conversations

## How to Use

This skill is designed to be invoked through a Claude conversation. Drop a Crossplay screenshot into the chat and ask Claude to solve it, or invoke it using `/crossplay-solver`. Then simply let Claude work and present the results.
Claude in the background will:

1. Run `grid_overlay.py` on your screenshot to number the cells
2. Read tile positions manually from the overlay
3. Verify the board by checking the last play's score
4. Show you an HTML board confirmation before solving
5. Run the solver and present the top moves visually

### Running locally
#### Requirements
- Python 3.8+
- `opencv-python`, `numpy`, `requests`

```bash
pip install opencv-python numpy requests
```

```bash
# 1. Build the dictionary (once per session)
python scripts/setup_dict.py --output dict.txt

# 2. Generate a grid overlay for reading tile positions
python scripts/grid_overlay.py screenshot.png -o overlay.png

# 3. Run the solver (board.json must be constructed manually or by Claude)
python scripts/solver.py \
    --board board.json \
    --rack AILETEC \
    --dict dict.txt \
    --top 10 \
    -q
```

#### `board.json` format

```json
{
  "tiles": {
    "7,7": "A",
    "7,8": "R",
    "7,9": "T"
  }
}
```

Keys are `"row,col"` (0-indexed, 0 = top-left).

