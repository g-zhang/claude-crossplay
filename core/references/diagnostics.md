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
blank status, and expected points.

The audit uses Tesseract first when a usable `tesseract` executable and its
`eng` language data are available. It thresholds the enlarged score corner at
180, places the dark glyph on a padded white canvas, and runs single-character
PSM 10 with a digit whitelist. A recognized score is compared directly with the
JSON claim. The audit records `tesseract` versus `topology` as the evidence
method in the PNG metadata.

The same optional executable provides a secondary letter check. After removing
the yellow last-move outline, the audit crops 15-80 percent of the source
tile's width and 10-85 percent of its height, resizes it to 120 by 120 pixels,
and runs PSM 10 with an `A-Z` whitelist at thresholds 180 and 190. Both passes
must return the same single uppercase letter. Agreement with JSON is `clear`;
disagreement is a required `review`; empty, multi-character, or disagreeing
output is `unavailable` and leaves the full source tile for visual review.
Confidence is not used because correct readings can have low reported
confidence on these small stylized glyphs. A stable reading is the preferred
correction for a conflicting transcription, but the audit only reports it and
never edits `board.json` itself.

Tesseract remains optional. If the executable is absent or returns no usable
digit, the audit counts enclosed loops in the score glyph at four thresholds
and compares stable topology with the JSON claim. This can confidently expose
0-versus-1/2/3/5/8 conflicts, including a normal uppercase tile whose corner
looks like 0. It deliberately marks 0 versus 4, 6, or 10 as ambiguous because
those values share one enclosed loop in the Crossplay font. An installed but
unusable Tesseract emits a warning before the topology fallback. If
`tesseract --list-langs` does not include `eng`, install the English model or
set `TESSDATA_PREFIX` to the directory containing `eng.traineddata`. Set
`CROSSPLAY_TESSERACT` to an executable name or path when Tesseract is not on
`PATH`; set it to `off` to disable OCR explicitly.

The script invokes Tesseract directly with list-form `subprocess.run`, streams
the prepared PNG through stdin, and reads stdout. `pytesseract` would still
require the same native executable and language data while adding Pillow and
temporary-file conversion, so it is not required for these narrow symbol
checks.

Treat a red letter or score warning as a required review, but do not treat the
absence of a warning as proof for an unavailable letter or ambiguous score.
Unstable topology is also shown as a visual check rather than silently treated
as clear. Implausibly empty or full threshold masks are unavailable instead of
being interpreted as zero-loop digits. The fallbacks assume the current bright
glyphs on darker tiles; revalidate their goldens if the app changes that font
or color treatment. The PNG carries the evidence and result in layout metadata
that the board-confirmation renderer validates before building theme-aware
cards which reflow across phone and desktop widths.

Board pages are designed to survive embedded viewers. Scripted output links
board cells and audit cards with buttons and `data-` targets instead of URL
fragments, so a sandboxed viewer never treats a same-page jump as external
navigation; `--no-script` output keeps plain `#` anchors and `:target`
highlighting. Board rasterization prefers a `blob:` URL and falls back to a
`data:` URL when a viewer's policy blocks blob images, and `Copy SVG` includes a
PNG flavor because document editors ignore the SVG flavor and would otherwise
paste raw markup. When a viewer blocks the Clipboard API by permissions policy,
the page removes its copy controls on load rather than showing buttons that can
only fail; the board and audit cards still render.

## Troubleshooting

- **Score mismatch:** Recheck column alignment, blank tiles, and the tile
  values in `game-rules.md`. When the reconstruction is too high, inspect the
  affected word's score corners for a displayed 0 that should be lowercase in
  JSON.
- **Letter mismatch:** Prefer the OCR letter and correct `board.json` unless
  the full source crop clearly disproves it. Check the score corner
  separately because the main letter cannot distinguish a blank.
- **No moves:** Recheck board reconstruction and confirm existing words are
  present in `dict.txt`.
- **Misaligned overlay:** Inspect the calibration diagnostics printed by
  `grid_overlay.py`. Expect roughly five matched anchors per axis, residuals
  below 3 pixels, and low axis disagreement.
- **False tile detections:** Increase the coverage threshold when premium
  squares are classified as tiles; decrease it when real tiles are missed.
- **Tile-audit mismatch:** A red card means the detector and `board.json`
  disagree about occupancy or the score evidence conflicts with the claimed
  points. Resolve it against the original screenshot before solving.
- **Input rejected:** Keep board coordinates within `0..14`, use one ASCII
  letter per occupied cell, represent existing blanks in lowercase, and pass a
  rack of one to seven `A-Z` or `?` tiles. The board and rack together may
  contain at most three blanks.
