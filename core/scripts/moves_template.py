"""
Shared HTML template for visual move boards.
Supports light and dark mode via prefers-color-scheme.
"""

from solver import TILE_PTS

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
  --new-border: #c47020;
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
    --new-border: #b86a15;
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
.cell.tile.blank{background:var(--tile-blank)}
.cell.new{background:var(--new-tile);color:#fff;border-radius:2px;box-shadow:inset 0 0 0 2px var(--new-border)}
.cell.star{background:var(--hdr-bg);font-size:13px;color:var(--star)}
.cell.empty{background:var(--cell-bg)}
.cell.prem{font-size:8px;font-weight:500}
.pts{position:absolute;bottom:0;right:1px;font-size:6px;opacity:0.75;font-weight:400}
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
        letter = new_tiles[key].upper()
        pts = TILE_PTS.get(letter, 0)
        return f'<div class="cell new">{letter}<span class="pts">{pts}</span></div>'
    elif key in board:
        letter = board[key].upper()
        is_blank = board[key].islower()
        pts = 0 if is_blank else TILE_PTS.get(letter, 0)
        cls = "cell tile blank" if is_blank else "cell tile"
        return f'<div class="{cls}">{letter}<span class="pts">{pts}</span></div>'
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

def _norm_tuple_keys(d):
    """Normalize dict keys to (r,c) tuples. Accepts both (r,c) tuples and 'r,c' strings."""
    out = {}
    for k, v in d.items():
        if isinstance(k, str):
            r, c = k.split(",")
            out[(int(r), int(c))] = v
        else:
            out[k] = v
    return out


def generate_board_confirm_html(board, premium, output_path, title="Board Confirmation", subtitle=""):
    """Generate an HTML page showing just the board for user confirmation (no moves)."""
    board = _norm_str_keys(board)
    premium = _norm_tuple_keys(premium)
    parts = [CSS, DARK_MODE_SCRIPT]
    parts.append(f'<h1>{title}</h1>')
    if subtitle:
        parts.append(f'<div class="subtitle">{subtitle}</div>')
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
  <div class="leg"><span class="leg-box" style="background:#FAECE7;border:1px solid #ddd;font-size:8px;display:flex;align-items:center;justify-content:center;color:#993C1D">3W</span> Triple Word</div>
  <div class="leg"><span class="leg-box" style="background:#FBEAF0;border:1px solid #ddd;font-size:8px;display:flex;align-items:center;justify-content:center;color:#993556">2W</span> Double Word</div>
  <div class="leg"><span class="leg-box" style="background:#E6F1FB;border:1px solid #ddd;font-size:8px;display:flex;align-items:center;justify-content:center;color:#185FA5">3L</span> Triple Letter</div>
  <div class="leg"><span class="leg-box" style="background:#EAF3DE;border:1px solid #ddd;font-size:8px;display:flex;align-items:center;justify-content:center;color:#3B6D11">2L</span> Double Letter</div>
</div>""")
    html = "\n".join(parts)
    with open(output_path, "w") as f:
        f.write(html)
    print(f"Board confirmation written to {output_path}")


def generate_moves_html(title, subtitle, board, premium, moves, output_path):
    """Generate full HTML page with move boards."""
    board = _norm_str_keys(board)
    premium = _norm_tuple_keys(premium)

    parts = [CSS, DARK_MODE_SCRIPT]

    parts.append(f'<h1>{title}</h1>')
    parts.append(f'<div class="subtitle">{subtitle}</div>')
    parts.append("""<div class="legend">
  <div class="leg"><span class="leg-box" style="background:var(--tile)"></span> Existing</div>
  <div class="leg"><span class="leg-box" style="background:var(--new-tile);box-shadow:inset 0 0 0 2px var(--new-border)"></span> Play here</div>
  <div class="leg"><span class="leg-box" style="background:#FAECE7;border:1px solid #ddd;font-size:8px;display:flex;align-items:center;justify-content:center;color:#993C1D">3W</span> Triple Word</div>
  <div class="leg"><span class="leg-box" style="background:#FBEAF0;border:1px solid #ddd;font-size:8px;display:flex;align-items:center;justify-content:center;color:#993556">2W</span> Double Word</div>
  <div class="leg"><span class="leg-box" style="background:#E6F1FB;border:1px solid #ddd;font-size:8px;display:flex;align-items:center;justify-content:center;color:#185FA5">3L</span> Triple Letter</div>
  <div class="leg"><span class="leg-box" style="background:#EAF3DE;border:1px solid #ddd;font-size:8px;display:flex;align-items:center;justify-content:center;color:#3B6D11">2L</span> Double Letter</div>
</div>""")

    for i, move in enumerate(moves):
        parts.append('<div class="move-section">')
        parts.append(f'<div class="move-header">#{i+1}: <strong>{move["word"]}</strong> — {move["pts"]} pts ({move["dir"]})</div>')
        parts.append('<div class="board"><div class="cell hdr"></div>')
        for c in range(15):
            parts.append(f'<div class="cell hdr">{c}</div>')
        for r in range(15):
            parts.append(f'<div class="cell hdr">{r}</div>')
            for c in range(15):
                parts.append(cell_html(r, c, board, move["tiles"], premium))
        parts.append('</div>')
        parts.append(f'<div class="move-info">Cross-words: {move["cross"]}</div>')
        parts.append(f'<div class="move-note">{move["note"]}</div>')
        parts.append('</div>')

    html = "\n".join(parts)
    with open(output_path, "w") as f:
        f.write(html)
    print(f"Written {len(moves)} moves to {output_path}")
