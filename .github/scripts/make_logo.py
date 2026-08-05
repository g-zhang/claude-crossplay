#!/usr/bin/env python3
"""Render the README logo as an SVG.

CROSSPLAY is drawn in the colour the boards use for tiles already played,
and LAUDE hangs off its opening C in the "play here" orange, so the logo
reads as a move being laid down. Colours come from the same theme variables
the solver's HTML boards use, so the logo restyles itself whenever that
palette changes. Re-run this after editing those variables in
core/scripts/moves_template.py.

    python .github/scripts/make_logo.py

Writes .github/assets/logo.svg. The logo paints no background, so the one
file works on a light or dark page and README.md can embed it directly
rather than pairing themed variants behind a <picture> element.
"""

import argparse
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "core" / "scripts"))

from moves_template import CSS  # noqa: E402
from solver import TILE_PTS  # noqa: E402

ACROSS_WORD = "CROSSPLAY"
# CLAUDE shares CROSSPLAY's opening C, so only these letters are drawn below
# it, and they carry the new-tile colour.
DOWN_TAIL = "LAUDE"

CELL = 44
GAP = 3
PAD = 6
RADIUS = 5
BORDER = 2
FONT = (
    "system-ui,-apple-system,'Segoe UI',Roboto,"
    "Helvetica,Arial,sans-serif"
)


def _theme_vars(block):
    """Pull '--name: value' declarations out of a CSS custom-property block."""
    return dict(re.findall(r"--([a-z0-9-]+):\s*([^;]+);", block))


def _light_vars():
    # CSS holds several :root blocks; the palette is the one defining --bg.
    for body in re.findall(r":root\s*\{(.*?)\}", CSS, re.S):
        if "--bg:" in body:
            return _theme_vars(body)
    raise SystemExit("could not locate the light theme block in CSS")


def _tiles():
    """Return (row, col, letter, is_new) for every tile in the logo."""
    out = [(0, i, letter, False) for i, letter in enumerate(ACROSS_WORD)]
    out += [(i + 1, 0, letter, True) for i, letter in enumerate(DOWN_TAIL)]
    return out


def _tile_svg(x, y, letter, is_new, palette):
    fill = palette["new-tile"] if is_new else palette["tile"]
    points = TILE_PTS.get(letter, 0)
    parts = [
        '<rect x="%d" y="%d" width="%d" height="%d" rx="%d" fill="%s"/>'
        % (x, y, CELL, CELL, RADIUS, fill)
    ]
    if is_new:
        # Matches the inset border the boards draw on a freshly placed tile.
        # SVG centres a stroke on its path, so inset the rect by half of it.
        parts.append(
            '<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="%.1f" '
            'fill="none" stroke="%s" stroke-width="%d"/>'
            % (x + BORDER / 2.0, y + BORDER / 2.0, CELL - BORDER,
               CELL - BORDER, RADIUS - BORDER / 2.0,
               palette["new-border"], BORDER)
        )
    parts.append(
        '<text x="%.1f" y="%.1f" font-family="%s" font-size="%.1f" '
        'font-weight="700" fill="#ffffff" text-anchor="middle" '
        'dominant-baseline="central">%s</text>'
        % (x + CELL / 2.0, y + CELL / 2.0 + CELL * 0.02, FONT,
           CELL * 0.48, letter)
    )
    parts.append(
        '<text x="%.1f" y="%.1f" font-family="%s" font-size="%.1f" '
        'font-weight="700" fill="#ffffff" fill-opacity="0.9" '
        'text-anchor="end">%d</text>'
        % (x + CELL - 5, y + 13, FONT, CELL * 0.22, points)
    )
    return "".join(parts)


def render(palette, out_path):
    tiles = _tiles()
    cols = max(c for _, c, _, _ in tiles) + 1
    rows = max(r for r, _, _, _ in tiles) + 1
    width = cols * CELL + (cols - 1) * GAP + PAD * 2
    height = rows * CELL + (rows - 1) * GAP + PAD * 2

    label = "%s %s spelled out in Crossplay tiles" % (
        ACROSS_WORD[:1] + DOWN_TAIL, ACROSS_WORD)
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" '
        'viewBox="0 0 %d %d" role="img" aria-label="%s">'
        % (width, height, width, height, label),
        "<title>claude-crossplay</title>",
    ]
    for r, c, letter, is_new in tiles:
        parts.append(_tile_svg(
            PAD + c * (CELL + GAP), PAD + r * (CELL + GAP),
            letter, is_new, palette))
    parts.append("</svg>")

    out_path.write_text("\n".join(parts) + "\n", encoding="utf-8")
    print("wrote %s (%dx%d)" % (out_path, width, height))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Render the README logo")
    parser.add_argument(
        "--out-dir",
        default=str(REPO / ".github" / "assets"),
        help="Directory to write logo.svg into",
    )
    args = parser.parse_args(argv)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    render(_light_vars(), out_dir / "logo.svg")


if __name__ == "__main__":
    main()
