# Solver and overlay diagnostics

Read this file only when the default workflow fails, performance needs a
limit, or engine equivalence is under investigation.

## Solver options

- `--engine trie` is the default. It prunes main-word prefixes and is the
  normal production choice.
- `--engine gaddag` is correctness-equivalent but usually slower in CPython.
- `--engine naive` retains the original cell-by-cell search for correctness
  comparisons.
- `--time-limit SECONDS` stops cooperatively and emits the best partial
  results found so far.
- `--no-prune` disables branch-and-bound for the naive engine only.
- `--full-board` and `--full-board-count N` print ASCII diagnostics.
- `--json-output PATH` writes the top moves in the schema consumed by
  `moves_template.py`.
- `-q` or `--quiet` suppresses the initial board print.

Trie and GADDAG indexes are built in memory from the validated dictionary on
each process start. The default trie takes little time to build and avoids
trusting stale or executable serialized cache files.

## Overlay calibration

`grid_overlay.py` locates the board by:

1. Finding a rough crop from edge projections.
2. Detecting saturation clusters along all four board edges.
3. Matching opposite-edge clusters to discard one-sided UI noise.
4. Fitting subsets to the known edge-premium positions `{0, 3, 7, 11, 14}`.
5. Comparing horizontal and vertical fits and using the lower-residual axis
   if they disagree by more than 5 percent.

A good fit normally has a residual below 3 pixels and horizontal and vertical
cell sizes within about 1 percent. Tile detection uses an HSV blue range and a
cell coverage threshold of 0.42.

With `--board-json` and `--tile-audit`, the script also creates one card for
every cell present in either the detector or the transcription. Each card shows
the full source tile, an enlarged top-right score corner, and the JSON letter,
blank status, and expected points. It does not OCR or infer the score; the audit
keeps image evidence and JSON claims side by side for explicit verification.
The PNG carries layout metadata that the board-confirmation renderer uses to
build theme-aware cards which reflow across phone and desktop widths.

## Troubleshooting

- **Score mismatch:** Recheck column alignment, blank tiles, and the tile
  values in `game-rules.md`. When the reconstruction is too high, inspect the
  affected word's score corners for a displayed 0 that should be lowercase in
  JSON.
- **No moves:** Recheck board reconstruction and confirm existing words are
  present in `dict.txt`.
- **Misaligned overlay:** Inspect the calibration diagnostics printed by
  `grid_overlay.py`. Expect roughly five matched anchors per axis, residuals
  below 3 pixels, and low axis disagreement.
- **False tile detections:** Increase the coverage threshold when premium
  squares are classified as tiles; decrease it when real tiles are missed.
- **Tile-audit mismatch:** A red card means the detector and `board.json`
  disagree about whether the cell is occupied. Resolve it against the original
  screenshot before solving.
- **Input rejected:** Keep board coordinates within `0..14`, use one ASCII
  letter per occupied cell, represent existing blanks in lowercase, and pass a
  rack of one to seven `A-Z` or `?` tiles. The board and rack together may
  contain at most three blanks.
