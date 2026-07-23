"""
Shared HTML template for visual move boards.
Supports light and dark mode via prefers-color-scheme.
"""

import argparse
import json
from html import escape
from pathlib import Path

from solver import PREMIUM, PREMIUM_DISPLAY, TILE_PTS


DEFAULT_PREMIUM = {
    position: PREMIUM_DISPLAY[premium_type]
    for position, premium_type in PREMIUM.items()
}

CSS = """<style>
*{box-sizing:border-box;margin:0;padding:0}

:root {
  --bg: #fafafa;
  --text: #222;
  --text-sec: #666;
  --text-note: #333;
  --note-bg: #f0f4f8;
  --grid-border: #bbb;
  --grid-bg: #ccc;
  --cell-bg: #fff;
  --hdr-bg: #f0f0f0;
  --hdr-text: #888;
  --divider: #4A90D9;
  --tile: #4A90D9;
  --tile-blank: #6BA3E0;
  --new-tile: #E8913A;
  --new-tile-blank: #F0A866;
  --new-border: #c47020;
  --blank-border: #ffe066;
  --blank-audit-bg: #fff4cc;
  --blank-audit-border: #c28a00;
  --star: #ccc;
}

@media (prefers-color-scheme: dark) {
  :root {
    --bg: #1a1a1a;
    --text: #e0e0e0;
    --text-sec: #aaa;
    --text-note: #ccc;
    --note-bg: #2a2d30;
    --grid-border: #555;
    --grid-bg: #333;
    --cell-bg: #222;
    --hdr-bg: #2a2a2a;
    --hdr-text: #888;
    --divider: #5a9fd4;
    --tile: #3d7ec0;
    --tile-blank: #5590c8;
    --new-tile: #d4801f;
    --new-tile-blank: #e09a3d;
    --new-border: #b86a15;
    --blank-border: #ffdc62;
    --blank-audit-bg: #3b3218;
    --blank-audit-border: #d8ad34;
    --star: #555;
  }
}

body{font-family:system-ui,-apple-system,sans-serif;padding:16px;background:var(--bg);color:var(--text)}
.move-section{margin-bottom:32px}
.move-header{font-size:18px;margin-bottom:8px;padding:8px 0;border-bottom:2px solid var(--divider);color:var(--text)}
.move-info{font-size:13px;color:var(--text-sec);margin-top:6px}
.move-note{font-size:13px;color:var(--text-note);margin-top:4px;padding:8px;background:var(--note-bg);border-radius:6px;line-height:1.5}
.board{display:grid;grid-template-columns:24px repeat(15,1fr);grid-template-rows:24px repeat(15,1fr);gap:1px;background:var(--grid-bg);border:1px solid var(--grid-border);border-radius:4px;overflow:hidden;max-width:540px;margin:4px 0}
.cell{display:flex;align-items:center;justify-content:center;background:var(--cell-bg);font-size:12px;font-weight:600;aspect-ratio:1;position:relative;min-width:0;overflow:hidden}
.cell.hdr{background:var(--hdr-bg);font-size:10px;color:var(--hdr-text);font-weight:400;aspect-ratio:auto}
.cell.tile{background:var(--tile);color:#fff;border-radius:2px}
.cell.tile.blank{background:var(--tile-blank);box-shadow:inset 0 0 0 2px var(--blank-border)}
.cell.new{background:var(--new-tile);color:#fff;border-radius:2px;box-shadow:inset 0 0 0 2px var(--new-border)}
.cell.new.blank{background:var(--new-tile-blank,#f0a866);box-shadow:inset 0 0 0 2px var(--blank-border)}
.cell.star{background:var(--hdr-bg);font-size:13px;color:var(--star)}
.cell.empty{background:var(--cell-bg)}
.cell.prem{font-size:8px;font-weight:500}
.pts{position:absolute;bottom:0;right:1px;font-size:6px;opacity:0.75;font-weight:400}
.cell.blank .pts{font-size:9px;opacity:1;font-weight:800;color:#fff}
.blank-mark{position:absolute;top:1px;left:2px;font-size:6px;line-height:1;font-weight:800;color:var(--blank-border)}
.blank-audit{max-width:540px;margin:0 0 12px;padding:10px 12px;border:2px solid var(--blank-audit-border);border-radius:6px;background:var(--blank-audit-bg);font-size:13px;line-height:1.45}
.blank-swatch{background:var(--tile-blank);box-shadow:inset 0 0 0 2px var(--blank-border);color:#fff;font-size:7px;font-weight:800;text-align:center;line-height:16px}
.legend{display:flex;gap:16px;margin:12px 0 24px;font-size:12px;color:var(--text-sec);flex-wrap:wrap}
.leg{display:flex;align-items:center;gap:4px}
.leg-box{width:16px;height:16px;border-radius:3px;display:inline-block}
h1{font-size:20px;font-weight:600;margin-bottom:4px;color:var(--text)}
.subtitle{font-size:14px;color:var(--text-sec);margin-bottom:16px}
</style>"""

PREM_COLORS_LIGHT = {
    "3W": ("#FAECE7", "#993C1D"),
    "2W": ("#FBEAF0", "#993556"),
    "3L": ("#E6F1FB", "#185FA5"),
    "2L": ("#EAF3DE", "#3B6D11"),
}

# Dark mode premium colors: darker bg, lighter text
PREM_COLORS_DARK = {
    "3W": ("#4A1B0C", "#F5C4B3"),
    "2W": ("#4B1528", "#F4C0D1"),
    "3L": ("#042C53", "#85B7EB"),
    "2L": ("#173404", "#C0DD97"),
}

DARK_MODE_SCRIPT = """<script>
const mq = window.matchMedia('(prefers-color-scheme: dark)');
function applyPrem(dark) {
  document.querySelectorAll('.prem[data-dark-bg]').forEach(el => {
    if (dark) {
      el.style.background = el.dataset.darkBg;
      el.style.color = el.dataset.darkFg;
    } else {
      el.style.background = el.dataset.lightBg;
      el.style.color = el.dataset.lightFg;
    }
  });
}
mq.addEventListener('change', e => applyPrem(e.matches));
document.addEventListener('DOMContentLoaded', () => applyPrem(mq.matches));
</script>"""


def prem_cell_html(prem_type):
    """Generate a premium square cell with light/dark support."""
    bg_l, fg_l = PREM_COLORS_LIGHT[prem_type]
    bg_d, fg_d = PREM_COLORS_DARK[prem_type]
    return (f'<div class="cell prem" style="background:{bg_l};color:{fg_l}"'
            f' data-light-bg="{bg_l}" data-light-fg="{fg_l}"'
            f' data-dark-bg="{bg_d}" data-dark-fg="{fg_d}">{prem_type}</div>')


def cell_html(r, c, board, new_tiles, premium):
    key = f"{r},{c}"
    if key in new_tiles:
        raw = new_tiles[key]
        letter = raw.upper()
        is_blank = raw.islower()
        pts = 0 if is_blank else TILE_PTS.get(letter, 0)
        cls = "cell new blank" if is_blank else "cell new"
        blank_mark = '<span class="blank-mark">B</span>' if is_blank else ""
        return (f'<div class="{cls}">{blank_mark}{escape(letter)}'
                f'<span class="pts">{pts}</span></div>')
    elif key in board:
        letter = board[key].upper()
        is_blank = board[key].islower()
        pts = 0 if is_blank else TILE_PTS.get(letter, 0)
        cls = "cell tile blank" if is_blank else "cell tile"
        blank_mark = '<span class="blank-mark">B</span>' if is_blank else ""
        return (f'<div class="{cls}">{blank_mark}{escape(letter)}'
                f'<span class="pts">{pts}</span></div>')
    else:
        prem = premium.get((r, c))
        if r == 7 and c == 7:
            return '<div class="cell star">&#9733;</div>'
        elif prem:
            return prem_cell_html(prem)
        else:
            return '<div class="cell empty"></div>'


def _norm_str_keys(d):
    """Normalize dict keys to 'r,c' strings. Accepts both (r,c) tuples and 'r,c' strings."""
    out = {}
    for k, v in d.items():
        if isinstance(k, tuple):
            out[f"{k[0]},{k[1]}"] = v
        else:
            out[k] = v
    return out

def _norm_premium(d):
    """Normalize premium keys and accept solver or display premium codes."""
    out = {}
    for k, v in d.items():
        if isinstance(k, str):
            r, c = k.split(",")
            key = (int(r), int(c))
        else:
            key = k
        label = PREMIUM_DISPLAY.get(v, v)
        if label not in PREM_COLORS_LIGHT:
            raise ValueError(f"Unsupported premium type: {v}")
        out[key] = label
    return out


def blank_audit_html(board):
    """Render an explicit, non-authoritative inventory of marked blanks."""
    marked = []
    for key, raw in board.items():
        if isinstance(raw, str) and raw.islower():
            row, col = key.split(",")
            marked.append((int(row), int(col), raw.upper()))
    marked.sort()

    if marked:
        labels = ", ".join(
            f"{escape(letter)} at ({row},{col})"
            for row, col, letter in marked
        )
        status = f"board.json marks {labels} as blank (0 points)."
    else:
        status = "board.json marks no blank tiles."

    return (
        '<div class="blank-audit"><strong>Blank audit:</strong> '
        f"{status} This is not automatic verification. Compare every "
        "tile-audit score corner with this board: each displayed 0 must be "
        "lowercase in JSON, and each lowercase tile must display 0.</div>"
    )


def _write_html(parts, output_path, message):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(parts), encoding="utf-8")
    print(f"{message}: {output_path}")


def generate_board_confirm_html(board, premium, output_path, title="Board Confirmation", subtitle=""):
    """Generate an HTML page showing just the board for user confirmation (no moves)."""
    board = _norm_str_keys(board)
    premium = _norm_premium(premium)
    parts = [CSS, DARK_MODE_SCRIPT]
    parts.append(f'<h1>{escape(str(title))}</h1>')
    if subtitle:
        parts.append(f'<div class="subtitle">{escape(str(subtitle))}</div>')
    parts.append(blank_audit_html(board))
    parts.append('<div class="board"><div class="cell hdr"></div>')
    for c in range(15):
        parts.append(f'<div class="cell hdr">{c}</div>')
    for r in range(15):
        parts.append(f'<div class="cell hdr">{r}</div>')
        for c in range(15):
            parts.append(cell_html(r, c, board, {}, premium))
    parts.append('</div>')
    parts.append("""<div class="legend">
  <div class="leg"><span class="leg-box" style="background:var(--tile)"></span> Tile</div>
  <div class="leg"><span class="leg-box blank-swatch">B0</span> Blank (0 points)</div>
  <div class="leg"><span class="leg-box" style="background:#FAECE7;border:1px solid #ddd;font-size:8px;display:flex;align-items:center;justify-content:center;color:#993C1D">3W</span> Triple Word</div>
  <div class="leg"><span class="leg-box" style="background:#FBEAF0;border:1px solid #ddd;font-size:8px;display:flex;align-items:center;justify-content:center;color:#993556">2W</span> Double Word</div>
  <div class="leg"><span class="leg-box" style="background:#E6F1FB;border:1px solid #ddd;font-size:8px;display:flex;align-items:center;justify-content:center;color:#185FA5">3L</span> Triple Letter</div>
  <div class="leg"><span class="leg-box" style="background:#EAF3DE;border:1px solid #ddd;font-size:8px;display:flex;align-items:center;justify-content:center;color:#3B6D11">2L</span> Double Letter</div>
</div>""")
    _write_html(parts, output_path, "Board confirmation written to")


def generate_moves_html(title, subtitle, board, premium, moves, output_path):
    """Generate full HTML page with move boards."""
    board = _norm_str_keys(board)
    premium = _norm_premium(premium)

    parts = [CSS, DARK_MODE_SCRIPT]

    parts.append(f'<h1>{escape(str(title))}</h1>')
    parts.append(f'<div class="subtitle">{escape(str(subtitle))}</div>')
    parts.append("""<div class="legend">
  <div class="leg"><span class="leg-box" style="background:var(--tile)"></span> Existing</div>
  <div class="leg"><span class="leg-box" style="background:var(--new-tile);box-shadow:inset 0 0 0 2px var(--new-border)"></span> Play here</div>
  <div class="leg"><span class="leg-box blank-swatch">B0</span> Blank (0 points)</div>
  <div class="leg"><span class="leg-box" style="background:#FAECE7;border:1px solid #ddd;font-size:8px;display:flex;align-items:center;justify-content:center;color:#993C1D">3W</span> Triple Word</div>
  <div class="leg"><span class="leg-box" style="background:#FBEAF0;border:1px solid #ddd;font-size:8px;display:flex;align-items:center;justify-content:center;color:#993556">2W</span> Double Word</div>
  <div class="leg"><span class="leg-box" style="background:#E6F1FB;border:1px solid #ddd;font-size:8px;display:flex;align-items:center;justify-content:center;color:#185FA5">3L</span> Triple Letter</div>
  <div class="leg"><span class="leg-box" style="background:#EAF3DE;border:1px solid #ddd;font-size:8px;display:flex;align-items:center;justify-content:center;color:#3B6D11">2L</span> Double Letter</div>
</div>""")

    for i, move in enumerate(moves):
        parts.append('<div class="move-section">')
        word = escape(str(move["word"]))
        points = escape(str(move["pts"]))
        direction = escape(str(move["dir"]))
        cross_words = escape(str(move["cross"]))
        note = escape(str(move["note"]))
        parts.append(f'<div class="move-header">#{i+1}: <strong>{word}</strong> -- {points} pts ({direction})</div>')
        parts.append('<div class="board"><div class="cell hdr"></div>')
        for c in range(15):
            parts.append(f'<div class="cell hdr">{c}</div>')
        for r in range(15):
            parts.append(f'<div class="cell hdr">{r}</div>')
            for c in range(15):
                parts.append(cell_html(r, c, board, move["tiles"], premium))
        parts.append('</div>')
        parts.append(f'<div class="move-info">Cross-words: {cross_words}</div>')
        parts.append(f'<div class="move-note">{note}</div>')
        parts.append('</div>')

    _write_html(parts, output_path, f"Written {len(moves)} moves to")


def _read_json(path):
    with Path(path).open("r", encoding="utf-8") as f:
        return json.load(f)


def _load_board(path):
    data = _read_json(path)
    board = data.get("tiles", data) if isinstance(data, dict) else None
    if not isinstance(board, dict):
        raise ValueError("Board JSON must be an object or contain a 'tiles' object")
    return board


def _load_moves(path):
    data = _read_json(path)
    moves = data.get("moves") if isinstance(data, dict) else data
    if not isinstance(moves, list):
        raise ValueError("Moves JSON must be an array or contain a 'moves' array")
    required = {"word", "pts", "dir", "tiles", "cross", "note"}
    for index, move in enumerate(moves, start=1):
        if not isinstance(move, dict):
            raise ValueError(f"Move {index} must be an object")
        missing = required - set(move)
        if missing:
            names = ", ".join(sorted(missing))
            raise ValueError(f"Move {index} is missing: {names}")
        if not isinstance(move["tiles"], dict):
            raise ValueError(f"Move {index} 'tiles' must be an object")
    return moves


def _add_common_arguments(parser, default_title):
    parser.add_argument("--board", required=True, help="Path to board JSON")
    parser.add_argument("--output", required=True, help="Output HTML path")
    parser.add_argument("--title", default=default_title)
    parser.add_argument("--subtitle", default="")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Render Crossplay board HTML")
    subparsers = parser.add_subparsers(dest="command", required=True)

    board_parser = subparsers.add_parser(
        "board", help="Render a board-confirmation page"
    )
    _add_common_arguments(board_parser, "Board Confirmation")

    moves_parser = subparsers.add_parser(
        "moves", help="Render move recommendations"
    )
    _add_common_arguments(moves_parser, "Crossplay Moves")
    moves_parser.add_argument("--moves", required=True, help="Path to moves JSON")

    args = parser.parse_args(argv)
    board = _load_board(args.board)
    if args.command == "board":
        generate_board_confirm_html(
            board,
            DEFAULT_PREMIUM,
            args.output,
            title=args.title,
            subtitle=args.subtitle,
        )
        return

    moves = _load_moves(args.moves)
    generate_moves_html(
        args.title,
        args.subtitle,
        board,
        DEFAULT_PREMIUM,
        moves,
        args.output,
    )


if __name__ == "__main__":
    main()
