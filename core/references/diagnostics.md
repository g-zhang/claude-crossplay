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

The first trie solve writes `<dictionary>.trie.pkl` beside the dictionary.
Delete that cache only after regenerating or replacing the dictionary.

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

## Troubleshooting

- **Score mismatch:** Recheck column alignment, blank tiles, and the tile
  values in `game-rules.md`.
- **No moves:** Recheck board reconstruction and confirm existing words are
  present in `dict.txt`.
- **Misaligned overlay:** Inspect the calibration diagnostics printed by
  `grid_overlay.py`. Expect roughly five matched anchors per axis, residuals
  below 3 pixels, and low axis disagreement.
- **False tile detections:** Increase the coverage threshold when premium
  squares are classified as tiles; decrease it when real tiles are missed.
- **Stale trie cache:** Remove `<dictionary>.trie.pkl` after changing the
  dictionary.
