"""
Shared HTML template for visual move boards.
Supports light and dark mode via prefers-color-scheme.
"""

import argparse
import base64
import json
from html import escape
from pathlib import Path

from solver import (
    PREMIUM,
    PREMIUM_DISPLAY,
    TILE_PTS,
    normalize_board_tiles,
)


DEFAULT_PREMIUM = {
    position: PREMIUM_DISPLAY[premium_type]
    for position, premium_type in PREMIUM.items()
}
AUDIT_METADATA_KEY = "crossplay-audit"
# Mirrors grid_overlay without importing its OpenCV rendering pipeline.
AUDIT_SCORE_POINT_HOLES = {
    0: 1,
    1: 0,
    2: 0,
    3: 0,
    4: 1,
    5: 0,
    6: 1,
    8: 2,
    10: 1,
}
LEGACY_AUDIT_LAYOUT = {
    "columns": 4,
    "page_header_height": 64,
    "card_width": 268,
    "card_height": 202,
    "image_size": 120,
    "image_top": 72,
    "whole_left": 8,
    "score_left": 140,
}

_DARK_THEME_VARS = """  --bg: #1a1a1a;
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
  --blank-border: #85b7eb;
  --blank-mark: #ffe0bd;
  --alert-mark: #f04438;
  --cell-hover: #dceeff;
  --board-highlight: #ffdc62;
  --blank-audit-bg: #3b3218;
  --blank-audit-border: #d8ad34;
  --star: #555;
  --surface: #242629;
  --surface-subtle: #1f2124;
  --surface-border: #454a50;
  --surface-shadow: 0 1px 2px rgba(0,0,0,.3);
  --audit-accent: #85b7eb;
  --audit-accent-bg: #102f4c;
  --audit-blank: #ffdc62;
  --audit-blank-bg: #3b3218;
  --audit-alert: #ff9b8f;
  --audit-alert-bg: #421f1c;
  --audit-ok: #a8d893;
  --audit-ok-bg: #20351c;"""

# Dark values apply on a dark system unless the reader forced light, and
# always when the reader forced dark.
_DARK_THEME_VARS_BLOCK = (
    "@media (prefers-color-scheme: dark) {\n"
    '  :root:not([data-theme="light"]) {\n'
    + _DARK_THEME_VARS
    + "\n  }\n}\n\n"
    ':root[data-theme="dark"] {\n'
    + _DARK_THEME_VARS
    + "\n}\n"
)


def _dark_theme_rule(selectors, declarations):
    """Apply a dark-mode rule for both automatic and forced dark themes."""
    targets = [selector.strip() for selector in selectors.split(",")]
    automatic = ",".join(
        f':root:not([data-theme="light"]) {target}' for target in targets
    )
    forced = ",".join(
        f':root[data-theme="dark"] {target}' for target in targets
    )
    return (
        "@media (prefers-color-scheme:dark){"
        f"{automatic}{declarations}"
        "}\n"
        f"{forced}{declarations}"
    )


CSS = """<style>
*{box-sizing:border-box;margin:0;padding:0}

/* Tell the user agent which scheme is live so it paints the canvas, form
   controls, and scrollbars to match, even inside an embedded viewer. */
:root{color-scheme:light dark}
:root[data-theme="light"]{color-scheme:light}
:root[data-theme="dark"]{color-scheme:dark}

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
  --blank-border: #4A90D9;
  --blank-mark: #ffe4c4;
  --alert-mark: #d92d20;
  --cell-hover: #185fa5;
  --board-highlight: #e8a600;
  --blank-audit-bg: #fff4cc;
  --blank-audit-border: #c28a00;
  --star: #ccc;
  --surface: #fff;
  --surface-subtle: #f4f6f8;
  --surface-border: #d7dde5;
  --surface-shadow: 0 1px 2px rgba(16,24,40,.06);
  --audit-accent: #185fa5;
  --audit-accent-bg: #e6f1fb;
  --audit-blank: #8a5a00;
  --audit-blank-bg: #fff4cc;
  --audit-alert: #b42318;
  --audit-alert-bg: #fff0ee;
  --audit-ok: #276719;
  --audit-ok-bg: #edf8e8;
}
""" + _DARK_THEME_VARS_BLOCK + """

html{background:var(--bg)}
body{font-family:system-ui,-apple-system,sans-serif;background:var(--bg);color:var(--text)}
/* Paint our own surface: an embedded viewer may inject this fragment into a
   host document whose own background would otherwise show through. */
.page{padding:16px;background:var(--bg);color:var(--text);min-height:100vh}
.move-section{margin-bottom:32px}
.move-header{font-size:18px;margin-bottom:8px;padding:8px 0;border-bottom:2px solid var(--divider);color:var(--text)}
.move-info{display:flex;gap:8px 18px;flex-wrap:wrap;font-size:13px;color:var(--text-sec);margin-top:6px}
.move-info strong{color:var(--text);font-weight:650}
.move-note{font-size:13px;color:var(--text-note);margin-top:4px;padding:8px;background:var(--note-bg);border-radius:6px;line-height:1.5}
.board{display:grid;grid-template-columns:24px repeat(15,1fr);grid-template-rows:24px repeat(15,1fr);gap:1px;background:var(--grid-bg);border:1px solid var(--grid-border);border-radius:4px;overflow:hidden;max-width:540px;margin:4px 0}
.cell{display:flex;align-items:center;justify-content:center;background:var(--cell-bg);font-size:12px;font-weight:600;aspect-ratio:1;position:relative;min-width:0;overflow:hidden}
.cell.hdr{background:var(--hdr-bg);font-size:10px;color:var(--hdr-text);font-weight:400;aspect-ratio:auto}
.cell.tile{background:var(--tile);color:#fff;border-radius:2px}
.cell.tile.blank{background:var(--tile-blank);box-shadow:inset 0 0 0 2px var(--blank-border)}
.cell.tile.alert{box-shadow:inset 0 0 0 1px var(--alert-mark)}
.cell.tile.blank.alert{box-shadow:inset 0 0 0 1px var(--alert-mark),inset 0 0 0 2px var(--blank-border)}
.cell.new{background:var(--new-tile);color:#fff;border-radius:2px;box-shadow:inset 0 0 0 2px var(--new-border)}
.cell.new.blank{background:var(--new-tile-blank,#f0a866);box-shadow:inset 0 0 0 2px var(--blank-border)}
.cell.star{background:var(--hdr-bg);font-size:13px;color:var(--star)}
.cell.empty{background:var(--cell-bg)}
.cell.prem{background:var(--prem-light-bg);color:var(--prem-light-fg);font-size:8px;font-weight:500}
.pts{position:absolute;top:2px;right:2px;font-size:8px;line-height:1;opacity:.9;font-weight:650}
.blank-mark{position:absolute;bottom:2px;left:2px;font-size:7px;line-height:1;font-weight:800;color:var(--blank-mark)}
.alert-mark{position:absolute;top:2px;left:2px;font-size:8px;line-height:1;font-weight:800;color:var(--alert-mark)}
.cell.audit-link{cursor:pointer;text-decoration:none}
button.cell{appearance:none;-webkit-appearance:none;border:0;font-family:inherit;line-height:inherit;text-align:center}
.cell.audit-link:hover,.cell.audit-link:focus-visible{z-index:1;outline:2px solid var(--cell-hover);outline-offset:-2px}
.cell.audit-link:target,.cell.audit-link.is-active{z-index:2;outline:3px solid var(--board-highlight);outline-offset:-2px}
.blank-audit{max-width:540px;margin:0 0 12px;padding:10px 12px;border:2px solid var(--blank-audit-border);border-radius:6px;background:var(--blank-audit-bg);font-size:13px;line-height:1.45}
.blank-swatch{background:var(--tile-blank);box-shadow:inset 0 0 0 2px var(--blank-border);color:#fff;font-size:7px;font-weight:650;text-align:center;line-height:16px}
.blank-swatch-mark{color:var(--blank-mark);font-weight:800}
.alert-swatch{background:var(--tile);box-shadow:inset 0 0 0 1px var(--alert-mark);text-align:center;line-height:16px}
.alert-swatch-mark{color:var(--alert-mark);font-size:8px;font-weight:800}
.legend{display:flex;gap:16px;margin:12px 0 24px;font-size:12px;color:var(--text-sec);flex-wrap:wrap}
.leg{display:flex;align-items:center;gap:4px}
.leg-box{width:16px;height:16px;border-radius:3px;display:inline-block}
.prem-swatch{display:flex;align-items:center;justify-content:center;border:1px solid var(--grid-border);background:var(--prem-light-bg);color:var(--prem-light-fg);font-size:8px}
h1{font-size:20px;font-weight:600;margin-bottom:4px;color:var(--text)}
.subtitle{font-size:14px;color:var(--text-sec);margin-bottom:16px}
.tile-audit-panel{max-width:540px;margin:28px 0 8px}
.audit-section-header{display:flex;align-items:flex-start;justify-content:space-between;gap:20px;padding:18px;border:1px solid var(--surface-border);border-radius:12px 12px 0 0;background:var(--surface)}
.audit-heading{flex:1;min-width:240px}
.audit-kicker{margin-bottom:4px;color:var(--audit-accent);font-size:11px;font-weight:700;letter-spacing:.08em;text-transform:uppercase}
.tile-audit-panel h2{font-size:20px;line-height:1.25;margin-bottom:6px;color:var(--text)}
.audit-intro{max-width:700px;color:var(--text-sec);font-size:13px;line-height:1.5}
.audit-summary{display:flex;justify-content:flex-end;gap:6px;flex-wrap:wrap}
.audit-chip{display:inline-flex;align-items:center;min-height:30px;padding:4px 9px;border:1px solid var(--surface-border);border-radius:999px;background:var(--surface-subtle);color:var(--text-sec);font-family:inherit;font-size:11px;font-weight:650;white-space:nowrap}
.audit-chip.blank{border-color:var(--audit-blank);background:var(--audit-blank-bg);color:var(--audit-blank)}
.audit-chip.ok{border-color:var(--audit-ok);background:var(--audit-ok-bg);color:var(--audit-ok)}
.audit-chip.alert{border-color:var(--audit-alert);background:var(--audit-alert-bg);color:var(--audit-alert)}
.audit-filter{cursor:pointer}
.audit-filter:hover{border-color:var(--audit-accent)}
.audit-filter:focus-visible{outline:2px solid var(--audit-accent);outline-offset:2px}
.audit-filter[aria-pressed="true"]{box-shadow:inset 0 0 0 2px currentColor}
.audit-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(180px,100%),1fr));gap:10px;padding:10px;border:1px solid var(--surface-border);border-top:0;border-radius:0 0 12px 12px;background:var(--surface-subtle)}
.audit-card{display:block;min-width:0;padding:9px;border:1px solid var(--surface-border);border-radius:10px;background:var(--surface);box-shadow:var(--surface-shadow);color:inherit;text-decoration:none;scroll-margin-top:16px}
.audit-card[hidden]{display:none}
.audit-card[href],.audit-card[role="button"]{cursor:pointer}
.audit-card.blank{border-color:var(--audit-blank)}
.audit-card.mismatch{border-color:var(--audit-alert);box-shadow:inset 0 3px 0 var(--audit-alert)}
.audit-card.score:not(.mismatch){border-color:var(--audit-blank)}
.audit-card:hover{border-color:var(--audit-accent)}
.audit-card:focus-visible{outline:2px solid var(--audit-accent);outline-offset:2px}
.audit-card:target,.audit-card.is-active{outline:3px solid var(--divider);outline-offset:2px}
.audit-card-top{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:9px}
.audit-coordinate{color:var(--text);font-size:12px;font-weight:750}
.audit-state{padding:4px 8px;border-radius:999px;background:var(--surface-subtle);color:var(--text-sec);font-size:13px;font-weight:750;line-height:1.2;white-space:nowrap}
.audit-card.blank .audit-state{background:var(--audit-blank-bg);color:var(--audit-blank)}
.audit-card.mismatch .audit-state{background:var(--audit-alert-bg);color:var(--audit-alert)}
.audit-comparison{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.audit-figure{min-width:0;padding:4px;border:1px solid var(--surface-border);border-radius:8px;background:var(--surface-subtle);text-align:center}
.audit-crop{width:var(--audit-crop-size);height:var(--audit-crop-size);max-width:100%;margin:0 auto;background-image:var(--audit-sheet);background-repeat:no-repeat;background-size:var(--audit-sheet-width) var(--audit-sheet-height);border-radius:5px}
.audit-figure figcaption{margin-top:5px;color:var(--text-sec);font-size:10px;font-weight:650}
.audit-claim{margin-top:8px;color:var(--text-sec);font-size:12px;line-height:1.4}
.audit-claim code{padding:1px 4px;border-radius:4px;background:var(--surface-subtle);color:var(--text);font-family:ui-monospace,SFMono-Regular,Consolas,monospace;font-size:12px;font-weight:700}
.audit-score-note,.audit-letter-note{display:block;margin-top:5px;font-weight:650}
.audit-score-note.review{color:var(--audit-alert)}
.audit-score-note.ambiguous{color:var(--audit-blank)}
.audit-score-note.unavailable{color:var(--text-sec)}
.audit-letter-note.review{color:var(--audit-alert)}
.audit-empty,.audit-filter-empty{grid-column:1/-1;padding:24px;color:var(--text-sec);font-size:13px;text-align:center}
.audit-filter-status{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}
.tile-audit-image-wrap{padding:12px;border:1px solid var(--surface-border);border-top:0;border-radius:0 0 12px 12px;background:var(--surface-subtle);overflow:auto}
.tile-audit-image{display:block;max-width:100%;height:auto;margin:auto;border:1px solid var(--surface-border);border-radius:8px;background:#fff}
@media (max-width:620px){
  .page{padding:12px}
  .audit-section-header{display:block;padding:14px}
  .audit-heading{min-width:0}
  .audit-summary{justify-content:flex-start;margin-top:12px}
  .audit-grid{grid-template-columns:1fr;padding:10px}
}
""" + _dark_theme_rule(
    ".cell.prem,.prem-swatch",
    "{background:var(--prem-dark-bg);color:var(--prem-dark-fg)}",
) + """
</style>"""

COPY_CSS = """<style>
.board-toolbar{display:flex;align-items:center;gap:8px;justify-content:flex-end;max-width:540px;margin-bottom:4px}
.copy-actions{display:flex;align-items:center;gap:4px;margin-left:auto}
.theme-actions{position:relative;display:inline-flex;align-items:center;padding:2px;border:1px solid var(--grid-border);border-radius:999px;background:var(--hdr-bg);margin-right:auto}
.theme-thumb{position:absolute;top:2px;left:2px;width:28px;height:22px;border-radius:999px;background:var(--surface);box-shadow:var(--surface-shadow);transition:transform .18s ease}
.theme-actions[data-active="auto"] .theme-thumb{transform:translateX(28px)}
.theme-actions[data-active="dark"] .theme-thumb{transform:translateX(56px)}
.theme-btn{position:relative;z-index:1;display:inline-flex;align-items:center;justify-content:center;width:28px;height:22px;padding:0;border:0;border-radius:999px;background:none;color:var(--text-sec);cursor:pointer}
.theme-btn:hover{color:var(--text)}
.theme-btn[aria-pressed="true"]{color:var(--audit-accent)}
.theme-btn:focus-visible{outline:2px solid var(--divider);outline-offset:2px}
.theme-icon{display:block;width:14px;height:14px}
@media (prefers-reduced-motion:reduce){.theme-thumb{transition:none}}
.copy-btn{border:1px solid var(--grid-border);border-radius:4px;background:var(--hdr-bg);color:var(--text);padding:2px 6px;font:inherit;font-size:11px;cursor:pointer}
.copy-btn:hover{border-color:var(--divider)}
.copy-btn:focus-visible{outline:2px solid var(--divider);outline-offset:2px}
.copy-btn:disabled{cursor:wait;opacity:.6}
.copy-status{color:var(--text-sec);font-size:11px;font-weight:400}
.copy-status.error{color:#b42318}
""" + _dark_theme_rule(".copy-status.error", "{color:#ff9b8f}") + """
@media print{.copy-actions,.theme-actions{display:none}}
</style>"""

MOVES_RESULT_CSS = """<style>
.cell.tile.blank,.cell.new.blank{background:var(--tile-blank);box-shadow:none}
.cell.blank .pts,.blank-swatch{font-weight:400}
.blank-swatch{box-shadow:none}
.move-header{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}
.move-title{min-width:0}
.move-section .cell.tile,.move-section .cell.new{cursor:default}
.move-section .cell.tile:hover,.move-section .cell.new:hover{z-index:1;outline:2px solid var(--cell-hover);outline-offset:-2px}
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

THEME_SCRIPT = r"""<script>
const THEME_STORAGE_KEY = 'crossplay-theme';
const THEME_CHOICES = ['auto', 'light', 'dark'];

function storedTheme() {
  try {
    const value = window.localStorage.getItem(THEME_STORAGE_KEY);
    return THEME_CHOICES.includes(value) ? value : 'auto';
  } catch (error) {
    // Embedded viewers can block storage; fall back to the system theme.
    return 'auto';
  }
}

function rememberTheme(choice) {
  try {
    window.localStorage.setItem(THEME_STORAGE_KEY, choice);
  } catch (error) {
    // Ignore storage failures; the choice still applies to this page.
  }
}

function applyTheme(choice) {
  const root = document.documentElement;
  if (choice === 'auto') {
    root.removeAttribute('data-theme');
  } else {
    root.setAttribute('data-theme', choice);
  }
  document.querySelectorAll('.theme-btn[data-theme-choice]').forEach(button => {
    button.setAttribute(
      'aria-pressed',
      String(button.dataset.themeChoice === choice)
    );
  });
  document.querySelectorAll('.theme-actions').forEach(group => {
    group.dataset.active = choice;
  });
}

function initTheme() {
  applyTheme(storedTheme());
}

document.addEventListener('click', event => {
  if (!(event.target instanceof Element)) {
    return;
  }
  const button = event.target.closest('.theme-btn[data-theme-choice]');
  if (!button) {
    return;
  }
  const choice = button.dataset.themeChoice;
  if (!THEME_CHOICES.includes(choice)) {
    throw new Error(`Unknown theme choice: ${choice}`);
  }
  applyTheme(choice);
  rememberTheme(choice);
});

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initTheme);
} else {
  initTheme();
}
</script>"""


BOARD_COPY_SCRIPT = r"""<script>
function legacyCopyText(text) {
  const holder = document.createElement('textarea');
  holder.setAttribute('aria-hidden', 'true');
  holder.style.cssText = 'position:fixed;left:-10000px;top:0';
  holder.value = text;
  document.body.appendChild(holder);
  holder.select();
  try {
    return document.execCommand('copy');
  } finally {
    holder.remove();
  }
}

function loadImage(url) {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve(image);
    image.onerror = () => reject(new Error('Could not render board image'));
    image.src = url;
  });
}

function canvasPngBlob(canvas) {
  return new Promise((resolve, reject) => {
    canvas.toBlob(blob => {
      if (blob) {
        resolve(blob);
      } else {
        reject(new Error('Could not encode board PNG'));
      }
    }, 'image/png');
  });
}

function escapeXml(value) {
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&apos;');
}

function boardSvgMarkup(board) {
  const boardRect = board.getBoundingClientRect();
  const boardStyle = getComputedStyle(board);
  const width = Math.ceil(boardRect.width);
  const height = Math.ceil(boardRect.height);
  const radius = parseFloat(boardStyle.borderTopLeftRadius) || 0;
  const parts = [
    `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}"`,
    ` viewBox="0 0 ${width} ${height}" shape-rendering="geometricPrecision">`,
    '<defs><clipPath id="board-clip">',
    `<rect width="${width}" height="${height}" rx="${radius}"/>`,
    '</clipPath></defs>',
    `<rect width="${width}" height="${height}" rx="${radius}"`,
    ` fill="${escapeXml(boardStyle.backgroundColor)}"/>`,
    '<g clip-path="url(#board-clip)">'
  ];

  board.querySelectorAll('.cell').forEach(cell => {
    const rect = cell.getBoundingClientRect();
    const style = getComputedStyle(cell);
    const x = rect.left - boardRect.left;
    const y = rect.top - boardRect.top;
    const cellRadius = parseFloat(style.borderTopLeftRadius) || 0;
    parts.push(
      `<rect x="${x}" y="${y}" width="${rect.width}" height="${rect.height}"`,
      ` rx="${cellRadius}" fill="${escapeXml(style.backgroundColor)}"/>`
    );

    if (style.boxShadow !== 'none' && style.boxShadow.includes('inset')) {
      const color = style.boxShadow.match(/rgba?\([^)]+\)|#[0-9a-fA-F]+/);
      if (color) {
        parts.push(
          `<rect x="${x + 1}" y="${y + 1}"`,
          ` width="${Math.max(0, rect.width - 2)}"`,
          ` height="${Math.max(0, rect.height - 2)}"`,
          ` rx="${Math.max(0, cellRadius - 1)}" fill="none"`,
          ` stroke="${escapeXml(color[0])}" stroke-width="2"/>`
        );
      }
    }

    const walker = document.createTreeWalker(cell, NodeFilter.SHOW_TEXT);
    while (walker.nextNode()) {
      const node = walker.currentNode;
      const text = node.nodeValue.trim();
      if (!text) {
        continue;
      }
      const range = document.createRange();
      range.selectNodeContents(node);
      const textRect = range.getBoundingClientRect();
      const textStyle = getComputedStyle(node.parentElement || cell);
      const textX = textRect.left - boardRect.left + textRect.width / 2;
      const textY = textRect.top - boardRect.top + textRect.height / 2;
      parts.push(
        `<text x="${textX}" y="${textY}" text-anchor="middle"`,
        ' dominant-baseline="middle"',
        ` fill="${escapeXml(textStyle.color)}"`,
        ` fill-opacity="${escapeXml(textStyle.opacity)}"`,
        ` font-family="${escapeXml(textStyle.fontFamily)}"`,
        ` font-size="${escapeXml(textStyle.fontSize)}"`,
        ` font-style="${escapeXml(textStyle.fontStyle)}"`,
        ` font-weight="${escapeXml(textStyle.fontWeight)}">`,
        `${escapeXml(text)}</text>`
      );
    }
  });
  parts.push('</g>');

  const borderWidth = parseFloat(boardStyle.borderTopWidth) || 0;
  if (borderWidth > 0) {
    const inset = borderWidth / 2;
    parts.push(
      `<rect x="${inset}" y="${inset}"`,
      ` width="${Math.max(0, width - borderWidth)}"`,
      ` height="${Math.max(0, height - borderWidth)}"`,
      ` rx="${Math.max(0, radius - inset)}" fill="none"`,
      ` stroke="${escapeXml(boardStyle.borderTopColor)}"`,
      ` stroke-width="${borderWidth}"/>`
    );
  }
  parts.push('</svg>');
  return parts.join('');
}

async function copySvgBoard(board) {
  const svg = boardSvgMarkup(board);
  const svgType = 'image/svg+xml';
  let clipboardError = null;
  if (navigator.clipboard && window.ClipboardItem) {
    const supportsType = type => typeof ClipboardItem.supports !== 'function'
      || ClipboardItem.supports(type);
    const svgBlob = () => new Blob([svg], {type: svgType});
    const textBlob = () => new Blob([svg], {type: 'text/plain'});
    const attempts = [];
    // Documents ignore the SVG flavor and would paste the raw markup, so
    // offer a PNG in the same item; vector tools still read the SVG.
    if (supportsType('image/png')) {
      const withPng = {
        'image/png': boardPngBlob(board),
        'text/plain': textBlob()
      };
      if (supportsType(svgType)) {
        withPng[svgType] = svgBlob();
      }
      attempts.push(withPng);
    }
    if (supportsType(svgType)) {
      attempts.push({[svgType]: svgBlob(), 'text/plain': textBlob()});
    }
    for (const payload of attempts) {
      try {
        await navigator.clipboard.write([new ClipboardItem(payload)]);
        return;
      } catch (error) {
        clipboardError = error;
      }
    }
  }
  if (navigator.clipboard && navigator.clipboard.writeText) {
    try {
      await navigator.clipboard.writeText(svg);
      return;
    } catch (error) {
      clipboardError = error;
    }
  }
  if (legacyCopyText(svg)) {
    return;
  }
  throw clipboardError || new Error('SVG clipboard copy is unavailable');
}

async function loadBoardSvgImage(svg) {
  const sources = [];
  try {
    sources.push({
      url: URL.createObjectURL(
        new Blob([svg], {type: 'image/svg+xml;charset=utf-8'})
      ),
      revoke: true
    });
  } catch (error) {
    // Object URLs are unavailable; the data URL below still works.
  }
  // Embedded viewers may block blob: images, so keep a data: URL fallback.
  sources.push({
    url: 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg),
    revoke: false
  });
  let lastError = null;
  for (const source of sources) {
    try {
      return {image: await loadImage(source.url), source};
    } catch (error) {
      lastError = error;
      if (source.revoke) {
        URL.revokeObjectURL(source.url);
      }
    }
  }
  throw lastError || new Error('Could not render board image');
}

async function boardPngBlob(board) {
  const rect = board.getBoundingClientRect();
  const width = Math.ceil(rect.width);
  const height = Math.ceil(rect.height);
  const svg = boardSvgMarkup(board);
  const {image, source} = await loadBoardSvgImage(svg);
  try {
    const scale = 2;
    const canvas = document.createElement('canvas');
    canvas.width = width * scale;
    canvas.height = height * scale;
    const context = canvas.getContext('2d');
    if (!context) {
      throw new Error('Canvas rendering is unavailable');
    }
    context.drawImage(image, 0, 0, canvas.width, canvas.height);
    return await canvasPngBlob(canvas);
  } finally {
    if (source.revoke) {
      URL.revokeObjectURL(source.url);
    }
  }
}

function clipboardPolicyBlocked() {
  const policy = document.featurePolicy || document.permissionsPolicy;
  if (policy && typeof policy.allowsFeature === 'function') {
    try {
      return !policy.allowsFeature('clipboard-write');
    } catch (error) {
      return false;
    }
  }
  return false;
}

function clipboardCopyAvailable() {
  if (!window.isSecureContext) {
    return false;
  }
  if (clipboardPolicyBlocked()) {
    return false;
  }
  return Boolean(
    navigator.clipboard && navigator.clipboard.write && window.ClipboardItem
  );
}

function disableCopyControls() {
  document.querySelectorAll('.copy-actions').forEach(actions => {
    const toolbar = actions.closest('.board-toolbar');
    actions.remove();
    if (toolbar && !toolbar.childElementCount) {
      toolbar.remove();
    }
  });
}

function initCopyControls() {
  // Embedded viewers can block the clipboard by permissions policy, so drop
  // the controls instead of offering a button that can only fail.
  if (!clipboardCopyAvailable()) {
    disableCopyControls();
  }
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initCopyControls);
} else {
  initCopyControls();
}

function copyErrorMessage(error) {
  if (!window.isSecureContext) {
    return 'Needs HTTPS or localhost';
  }
  if (error && error.name === 'NotAllowedError') {
    return 'Clipboard permission denied';
  }
  return 'Copy failed';
}

function boardExportContainer(button) {
  const container = button.closest('[data-board-export]');
  if (!container) {
    throw new Error('Board export container is missing');
  }
  return container;
}

function showCopyStatus(button, message, isError) {
  const status = boardExportContainer(button).querySelector('.copy-status');
  if (!status) {
    throw new Error('Board export status is missing');
  }
  window.clearTimeout(Number(status.dataset.timer || 0));
  status.textContent = message;
  status.classList.toggle('error', isError);
  status.dataset.timer = String(window.setTimeout(() => {
    status.textContent = '';
    status.classList.remove('error');
  }, 3000));
}

async function handleBoardCopy(button) {
  const board = boardExportContainer(button).querySelector('.board');
  if (!board) {
    throw new Error('Board export target is missing');
  }
  const format = button.dataset.copyFormat;
  button.disabled = true;
  showCopyStatus(button, 'Copying...', false);
  try {
    if (format === 'svg') {
      await copySvgBoard(board);
      showCopyStatus(button, 'SVG copied', false);
    } else if (format === 'png') {
      if (!navigator.clipboard || !window.ClipboardItem) {
        throw new Error('PNG clipboard copy is unavailable');
      }
      const png = await boardPngBlob(board);
      await navigator.clipboard.write([
        new ClipboardItem({'image/png': png})
      ]);
      showCopyStatus(button, 'PNG copied', false);
    } else {
      throw new Error(`Unknown copy format: ${format}`);
    }
  } catch (error) {
    console.error(error);
    if (
      error
      && error.name === 'NotAllowedError'
      && (clipboardPolicyBlocked() || !navigator.clipboard)
    ) {
      disableCopyControls();
      return;
    }
    showCopyStatus(button, copyErrorMessage(error), true);
  } finally {
    button.disabled = false;
  }
}

document.addEventListener('click', event => {
  if (!(event.target instanceof Element)) {
    return;
  }
  const button = event.target.closest('.copy-btn[data-copy-format]');
  if (button) {
    void handleBoardCopy(button);
  }
});
</script>"""


AUDIT_SCRIPT = r"""<script>
function handleAuditFilter(button) {
  const panel = button.closest('.tile-audit-panel');
  if (!panel) {
    throw new Error('Tile audit panel is missing');
  }
  const filter = button.dataset.auditFilter;
  if (!['all', 'blank', 'mismatch', 'letter', 'score'].includes(filter)) {
    throw new Error(`Unknown tile audit filter: ${filter}`);
  }
  const cards = Array.from(panel.querySelectorAll('.audit-card'));
  let visibleCount = 0;
  cards.forEach(card => {
    const visible = filter === 'all' || card.classList.contains(filter);
    card.hidden = !visible;
    if (visible) {
      visibleCount += 1;
    }
  });
  panel.querySelectorAll('.audit-filter').forEach(control => {
    control.setAttribute(
      'aria-pressed',
      String(control.dataset.auditFilter === filter)
    );
  });
  const empty = panel.querySelector('.audit-filter-empty');
  if (empty) {
    empty.hidden = visibleCount !== 0;
  }
  const status = panel.querySelector('.audit-filter-status');
  if (status) {
    const suffix = visibleCount === 1 ? 'tile' : 'tiles';
    status.textContent = `${visibleCount} audit ${suffix} shown`;
  }
}

function clearAuditHighlights() {
  document.querySelectorAll('.is-active').forEach(node => {
    node.classList.remove('is-active');
  });
}

function scrollBehavior() {
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches
    ? 'auto'
    : 'smooth';
}

function revealAuditTarget(control) {
  const target = document.getElementById(control.dataset.auditTarget);
  if (!target) {
    return;
  }
  const panel = target.closest('.tile-audit-panel');
  const allButton = panel && panel.querySelector(
    '.audit-filter[data-audit-filter="all"]'
  );
  if (allButton) {
    handleAuditFilter(allButton);
  }
  clearAuditHighlights();
  target.classList.add('is-active');
  target.focus({preventScroll: true});
  const behavior = scrollBehavior();
  requestAnimationFrame(() => {
    target.scrollIntoView({behavior, block: 'center'});
  });
}

function revealBoardTarget(control) {
  const target = document.getElementById(control.dataset.boardTarget);
  const board = target && target.closest('.board');
  if (!target || !board) {
    return;
  }
  clearAuditHighlights();
  target.classList.add('is-active');
  target.focus({preventScroll: true});
  const behavior = scrollBehavior();
  requestAnimationFrame(() => {
    board.scrollIntoView({behavior, block: 'start'});
  });
}

document.addEventListener('click', event => {
  if (!(event.target instanceof Element)) {
    return;
  }
  const filter = event.target.closest('.audit-filter[data-audit-filter]');
  if (filter) {
    handleAuditFilter(filter);
    return;
  }
  const auditControl = event.target.closest(
    '.audit-link[data-audit-target]'
  );
  if (auditControl) {
    revealAuditTarget(auditControl);
    return;
  }
  const boardControl = event.target.closest(
    '.audit-card[data-board-target]'
  );
  if (boardControl) {
    revealBoardTarget(boardControl);
  }
});

document.addEventListener('keydown', event => {
  if (event.key !== 'Enter' && event.key !== ' ') {
    return;
  }
  if (!(event.target instanceof Element)) {
    return;
  }
  const boardControl = event.target.closest(
    '.audit-card[data-board-target]'
  );
  if (!boardControl) {
    return;
  }
  event.preventDefault();
  revealBoardTarget(boardControl);
});
</script>"""


def prem_cell_html(prem_type):
    """Generate a premium square cell with light/dark support."""
    bg_l, fg_l = PREM_COLORS_LIGHT[prem_type]
    bg_d, fg_d = PREM_COLORS_DARK[prem_type]
    return (
        '<div class="cell prem" '
        f'style="--prem-light-bg:{bg_l};--prem-light-fg:{fg_l};'
        f'--prem-dark-bg:{bg_d};--prem-dark-fg:{fg_d}">'
        f"{prem_type}</div>"
    )


def _tile_cell_html(
        r, c, raw, cell_class, link_to_audit=False,
        show_blank_mark=True, include_scripts=True, needs_review=False):
    letter = raw.upper()
    is_blank = raw.islower()
    pts = 0 if is_blank else TILE_PTS.get(letter, 0)
    blank_mark = (
        '<span class="blank-mark">B</span>'
        if is_blank and show_blank_mark
        else ""
    )
    alert_mark = (
        '<span class="alert-mark" aria-hidden="true">!</span>'
        if needs_review
        else ""
    )
    tag = "div"
    attributes = f'class="{cell_class}"'
    if needs_review:
        cell_class = f"{cell_class} alert"
        attributes = f'class="{cell_class}"'
    if link_to_audit:
        kind = "blank tile" if is_blank else "tile"
        review = " needing review" if needs_review else ""
        label = (
            f'aria-label="View source audit for {kind} '
            f'{escape(letter)} at row {r}, column {c}{review}"'
        )
        if include_scripts:
            # A button keeps the jump in-document, so embedded viewers do not
            # treat a fragment link as external navigation.
            tag = "button"
            attributes = (
                f'type="button" id="board-cell-{r}-{c}" '
                f'class="{cell_class} audit-link" '
                f'data-audit-target="audit-{r}-{c}" {label}'
            )
        else:
            tag = "a"
            attributes = (
                f'id="board-cell-{r}-{c}" class="{cell_class} audit-link" '
                f'href="#audit-{r}-{c}" {label}'
            )
    return (
        f"<{tag} {attributes}>{alert_mark}{blank_mark}{escape(letter)}"
        f'<span class="pts">{pts}</span></{tag}>'
    )


def cell_html(
        r, c, board, new_tiles, premium, audit_targets=None,
        show_blank_mark=True, include_scripts=True, audit_alerts=None):
    key = f"{r},{c}"
    if key in new_tiles:
        raw = new_tiles[key]
        is_blank = raw.islower()
        cls = "cell new blank" if is_blank else "cell new"
        return _tile_cell_html(
            r,
            c,
            raw,
            cls,
            show_blank_mark=show_blank_mark,
        )
    elif key in board:
        raw = board[key]
        is_blank = raw.islower()
        cls = "cell tile blank" if is_blank else "cell tile"
        return _tile_cell_html(
            r,
            c,
            raw,
            cls,
            link_to_audit=(
                audit_targets is not None and (r, c) in audit_targets
            ),
            show_blank_mark=show_blank_mark,
            include_scripts=include_scripts,
            needs_review=(
                audit_alerts is not None and (r, c) in audit_alerts
            ),
        )
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


THEME_ICONS = {
    "light": (
        '<svg class="theme-icon" viewBox="0 0 24 24" fill="none" '
        'stroke="currentColor" stroke-width="2" stroke-linecap="round" '
        'aria-hidden="true"><circle cx="12" cy="12" r="4.2"/>'
        '<path d="M12 2.2v2.1M12 19.7v2.1M4.1 4.1l1.5 1.5M18.4 18.4l1.5 1.5'
        'M2.2 12h2.1M19.7 12h2.1M4.1 19.9l1.5-1.5M18.4 5.6l1.5-1.5"/></svg>'
    ),
    "auto": (
        '<svg class="theme-icon" viewBox="0 0 24 24" fill="none" '
        'stroke="currentColor" stroke-width="2" aria-hidden="true">'
        '<circle cx="12" cy="12" r="9"/>'
        '<text x="12" y="16.6" text-anchor="middle" font-size="13" '
        'font-weight="700" font-family="system-ui,sans-serif" '
        'fill="currentColor" stroke="none">A</text></svg>'
    ),
    "dark": (
        '<svg class="theme-icon" viewBox="0 0 24 24" fill="currentColor" '
        'aria-hidden="true"><path d="M20.6 15.1A8.7 8.7 0 0 1 8.9 3.4'
        'a8.7 8.7 0 1 0 11.7 11.7Z"/></svg>'
    ),
}


def _occupied_coordinates(*tile_maps):
    """Collect board coordinates covered by any of the given tile maps."""
    occupied = set()
    for tiles in tile_maps:
        for key in tiles:
            row, col = (int(part) for part in key.split(","))
            occupied.add((row, col))
    return occupied


def _visible_premium_types(premium, occupied):
    """Premium codes still visible, since tiles and the star hide the rest."""
    return {
        code
        for (row, col), code in premium.items()
        if (row, col) not in occupied and (row, col) != (7, 7)
    }


def _has_blank(*tile_maps):
    return any(
        isinstance(raw, str) and raw.islower()
        for tiles in tile_maps
        for raw in tiles.values()
    )


def _legend_html(entries):
    """Render a legend, omitting anything the rendered boards do not show."""
    if not entries:
        return ""
    body = "\n  ".join(entries)
    return f'<div class="legend">\n  {body}\n</div>'


def _legend_prem_html(visible=None):
    """Render premium legend swatches from the shared theme color tables."""
    labels = (
        ("3W", "Triple Word"),
        ("2W", "Double Word"),
        ("3L", "Triple Letter"),
        ("2L", "Double Letter"),
    )
    entries = []
    for prem_type, label in labels:
        if visible is not None and prem_type not in visible:
            continue
        bg_l, fg_l = PREM_COLORS_LIGHT[prem_type]
        bg_d, fg_d = PREM_COLORS_DARK[prem_type]
        entries.append(
            '<div class="leg"><span class="leg-box prem-swatch" '
            f'style="--prem-light-bg:{bg_l};--prem-light-fg:{fg_l};'
            f'--prem-dark-bg:{bg_d};--prem-dark-fg:{fg_d}">{prem_type}</span> '
            f"{label}</div>"
        )
    return entries


def _theme_actions_html():
    buttons = "".join(
        f'<button type="button" class="theme-btn" '
        f'data-theme-choice="{choice}" aria-pressed="'
        f'{"true" if choice == "auto" else "false"}" '
        f'aria-label="{label} theme" title="{label} theme">'
        f'{THEME_ICONS[choice]}</button>'
        for choice, label in (
            ("light", "Light"),
            ("auto", "Automatic"),
            ("dark", "Dark"),
        )
    )
    return (
        '<span class="theme-actions" role="group" aria-label="Color theme" '
        'data-active="auto"><span class="theme-thumb" aria-hidden="true">'
        f'</span>{buttons}</span>'
    )


def _copy_actions_html():
    return (
        '<span class="copy-actions">'
        '<button type="button" class="copy-btn" '
        'data-copy-format="svg" aria-label="Copy board as SVG" '
        'title="Copy board as SVG">SVG</button>'
        '<button type="button" class="copy-btn" '
        'data-copy-format="png" aria-label="Copy board as PNG" '
        'title="Copy board as PNG">PNG</button>'
        '<span class="copy-status" role="status" '
        'aria-live="polite"></span></span>'
    )


def _png_info(image_bytes):
    signature = b"\x89PNG\r\n\x1a\n"
    if not image_bytes.startswith(signature):
        raise ValueError("Tile audit PNG has an invalid signature")

    width = None
    height = None
    text_chunks = {}
    offset = len(signature)
    while offset + 12 <= len(image_bytes):
        length = int.from_bytes(image_bytes[offset:offset + 4], "big")
        chunk_type = image_bytes[offset + 4:offset + 8]
        data_start = offset + 8
        data_end = data_start + length
        chunk_end = data_end + 4
        if chunk_end > len(image_bytes):
            raise ValueError("Tile audit PNG contains a truncated chunk")
        chunk_data = image_bytes[data_start:data_end]
        if chunk_type == b"IHDR":
            if length != 13:
                raise ValueError("Tile audit PNG has an invalid IHDR chunk")
            width = int.from_bytes(chunk_data[0:4], "big")
            height = int.from_bytes(chunk_data[4:8], "big")
        elif chunk_type == b"tEXt":
            keyword, separator, value = chunk_data.partition(b"\0")
            if separator:
                text_chunks[keyword.decode("latin-1")] = value.decode(
                    "latin-1"
                )
        elif chunk_type == b"IEND":
            break
        offset = chunk_end

    if width is None or height is None:
        raise ValueError("Tile audit PNG is missing image dimensions")
    return width, height, text_chunks


def _validate_letter_evidence(entry):
    letter_check = entry["letter_check"]
    if (
            not isinstance(letter_check, str)
            or letter_check not in {"clear", "review", "unavailable"}):
        raise ValueError("Tile audit PNG entry has invalid letter check")
    letter_method = entry["letter_method"]
    if (
            not isinstance(letter_method, str)
            or letter_method not in {"tesseract", "none"}):
        raise ValueError("Tile audit PNG entry has invalid letter method")
    letter_ocr = entry["letter_ocr"]
    if (
            letter_ocr is not None
            and (
                not isinstance(letter_ocr, str)
                or len(letter_ocr) != 1
                or not letter_ocr.isascii()
                or not "A" <= letter_ocr <= "Z")):
        raise ValueError("Tile audit PNG entry has invalid OCR letter")
    reason = entry["letter_reason"]
    if not isinstance(reason, str) or not reason or len(reason) > 300:
        raise ValueError("Tile audit PNG entry has invalid letter reason")
    if not entry["transcribed"]:
        if (
                letter_check != "unavailable"
                or letter_method != "none"
                or letter_ocr is not None):
            raise ValueError(
                "Tile audit PNG entry has letter evidence "
                "for an untranscribed tile"
            )
        return
    if letter_check == "unavailable":
        if letter_method != "none" or letter_ocr is not None:
            raise ValueError(
                "Tile audit PNG entry has invalid letter evidence"
            )
        return
    if letter_method != "tesseract" or letter_ocr is None:
        raise ValueError("Tile audit PNG entry has invalid letter evidence")
    expected_check = (
        "clear"
        if letter_ocr == entry["letter"].upper()
        else "review"
    )
    if letter_check != expected_check:
        raise ValueError(
            "Tile audit PNG entry has invalid letter semantics"
        )


def _validate_audit_manifest(manifest, width, height):
    if not isinstance(manifest, dict) or manifest.get("version") != 1:
        raise ValueError("Tile audit PNG has unsupported responsive metadata")
    sheet = manifest.get("sheet")
    layout = manifest.get("layout")
    entries = manifest.get("entries")
    if not isinstance(sheet, dict) or not isinstance(layout, dict):
        raise ValueError("Tile audit PNG metadata is missing layout data")
    if not isinstance(entries, list) or len(entries) > 225:
        raise ValueError("Tile audit PNG metadata has invalid entries")
    if type(manifest.get("detection_known")) is not bool:
        raise ValueError("Tile audit PNG has invalid detection metadata")
    if sheet.get("width") != width or sheet.get("height") != height:
        raise ValueError("Tile audit PNG metadata dimensions do not match")

    layout_keys = (
        "columns",
        "page_header_height",
        "card_width",
        "card_height",
        "image_size",
        "image_top",
        "whole_left",
        "score_left",
    )
    for key in layout_keys:
        value = layout.get(key)
        if type(value) is not int or value <= 0:
            raise ValueError(f"Tile audit PNG has invalid layout field: {key}")
    if (
            layout["whole_left"] + layout["image_size"]
            > layout["card_width"]
            or layout["score_left"] + layout["image_size"]
            > layout["card_width"]
            or layout["image_top"] + layout["image_size"]
            > layout["card_height"]):
        raise ValueError("Tile audit PNG crop layout exceeds its card bounds")
    rows = max(
        1,
        (len(entries) + layout["columns"] - 1) // layout["columns"],
    )
    if (
            width != layout["columns"] * layout["card_width"]
            or height != (
                layout["page_header_height"] + rows * layout["card_height"]
            )):
        raise ValueError("Tile audit PNG layout does not match its sheet")

    seen = set()
    score_metadata_modes = set()
    letter_metadata_modes = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("Tile audit PNG contains an invalid entry")
        row = entry.get("row")
        col = entry.get("col")
        if (
                type(row) is not int
                or type(col) is not int
                or not 0 <= row < 15
                or not 0 <= col < 15
                or (row, col) in seen):
            raise ValueError("Tile audit PNG contains invalid coordinates")
        seen.add((row, col))
        for key in ("detected", "transcribed", "blank"):
            if type(entry.get(key)) is not bool:
                raise ValueError(
                    f"Tile audit PNG entry has invalid field: {key}"
                )
        letter = entry.get("letter")
        if "letter" not in entry:
            raise ValueError("Tile audit PNG entry is missing letter")
        if entry["transcribed"]:
            if (
                    not isinstance(letter, str)
                    or len(letter) != 1
                    or not letter.isascii()
                    or not letter.isalpha()):
                raise ValueError("Tile audit PNG entry has invalid letter")
        elif letter is not None:
            raise ValueError("Untranscribed tile audit entry has a letter")
        points = entry.get("points")
        if "points" not in entry:
            raise ValueError("Tile audit PNG entry is missing points")
        if points is not None and (type(points) is not int or points < 0):
            raise ValueError("Tile audit PNG entry has invalid points")
        if entry["blank"] and not entry["transcribed"]:
            raise ValueError("Untranscribed tile audit entry cannot be blank")
        if entry["transcribed"] and points is None:
            raise ValueError("Transcribed tile audit entry is missing points")
        if entry["transcribed"]:
            expected_points = (
                0 if entry["blank"] else TILE_PTS.get(letter.upper())
            )
            if points != expected_points:
                raise ValueError(
                    "Tile audit PNG entry has inconsistent points"
                )
        score_fields = {
            "score_check",
            "score_holes",
            "score_method",
            "score_ocr_digit",
            "score_reason",
        }
        score_metadata_present = any(
            key in entry for key in score_fields
        )
        score_metadata_modes.add(score_metadata_present)
        if (
                score_metadata_present
                and not score_fields.issubset(entry)):
            raise ValueError(
                "Tile audit PNG entry has incomplete score evidence"
            )
        if score_metadata_present:
            score_check = entry["score_check"]
            if (
                    not isinstance(score_check, str)
                    or score_check not in {
                        "clear", "ambiguous", "review", "unavailable"
                    }):
                raise ValueError(
                    "Tile audit PNG entry has invalid score check"
                )
            score_holes = entry["score_holes"]
            if (
                    score_holes is not None
                    and (type(score_holes) is not int or score_holes < 0)):
                raise ValueError(
                    "Tile audit PNG entry has invalid score topology"
                )
            score_method = entry["score_method"]
            score_ocr_digit = entry["score_ocr_digit"]
            if (
                    not isinstance(score_method, str)
                    or score_method not in {
                        "none", "tesseract", "topology"
                    }):
                raise ValueError(
                    "Tile audit PNG entry has invalid score method"
                )
            if (
                    score_ocr_digit is not None
                    and (
                        type(score_ocr_digit) is not int
                        or not 0 <= score_ocr_digit <= 10)):
                raise ValueError(
                    "Tile audit PNG entry has invalid OCR score"
                )
            if score_method == "tesseract":
                if (
                        not entry["transcribed"]
                        or score_ocr_digit is None
                        or score_holes is not None
                        or score_check != (
                            "clear"
                            if score_ocr_digit == points
                            else "review"
                        )):
                    raise ValueError(
                        "Tile audit PNG entry has invalid OCR evidence"
                    )
            elif score_ocr_digit is not None:
                raise ValueError(
                    "Tile audit PNG entry has unexpected OCR evidence"
                )
            elif score_method == "none":
                if score_check != "unavailable" or score_holes is not None:
                    raise ValueError(
                        "Tile audit PNG entry has invalid score evidence"
                    )
            else:
                if not entry["transcribed"]:
                    raise ValueError(
                        "Tile audit PNG entry has invalid topology evidence"
                    )
                natural_points = TILE_PTS.get(letter.upper())
                alternative_points = (
                    natural_points if entry["blank"] else 0
                )
                expected_holes = AUDIT_SCORE_POINT_HOLES[points]
                alternative_holes = AUDIT_SCORE_POINT_HOLES[
                    alternative_points
                ]
                if expected_holes == alternative_holes:
                    expected_check = "ambiguous"
                elif score_holes is None:
                    expected_check = "unavailable"
                elif score_holes == expected_holes:
                    expected_check = "clear"
                else:
                    expected_check = "review"
                if score_check != expected_check:
                    raise ValueError(
                        "Tile audit PNG entry has invalid topology evidence"
                    )
            score_reason = entry["score_reason"]
            if (
                    not isinstance(score_reason, str)
                    or not score_reason
                    or len(score_reason) > 300):
                raise ValueError(
                    "Tile audit PNG entry has invalid score reason"
                )
        letter_fields = {
            "letter_check",
            "letter_method",
            "letter_ocr",
            "letter_reason",
        }
        letter_metadata_present = any(
            key in entry for key in letter_fields
        )
        letter_metadata_modes.add(letter_metadata_present)
        if (
                letter_metadata_present
                and not letter_fields.issubset(entry)):
            raise ValueError(
                "Tile audit PNG entry has incomplete letter evidence"
            )
        if letter_metadata_present:
            _validate_letter_evidence(entry)
    if len(score_metadata_modes) > 1:
        raise ValueError("Tile audit PNG mixes score evidence schemas")
    if len(letter_metadata_modes) > 1:
        raise ValueError("Tile audit PNG mixes letter evidence schemas")
    return manifest


def _legacy_audit_manifest(board, width, height):
    entries = []
    positions = sorted(
        (
            (int(row), int(col), raw)
            for key, raw in board.items()
            for row, col in [key.split(",")]
            if isinstance(raw, str) and raw != "."
        ),
        key=lambda item: (item[0], item[1]),
    )
    for row, col, raw in positions:
        is_blank = raw.islower()
        letter = raw.upper()
        entries.append({
            "row": row,
            "col": col,
            "detected": True,
            "transcribed": True,
            "letter": letter,
            "blank": is_blank,
            "points": 0 if is_blank else TILE_PTS.get(letter, 0),
        })

    layout = dict(LEGACY_AUDIT_LAYOUT)
    rows = max(1, (len(entries) + layout["columns"] - 1)
               // layout["columns"])
    expected_width = layout["columns"] * layout["card_width"]
    expected_height = (
        layout["page_header_height"] + rows * layout["card_height"]
    )
    if width != expected_width or height != expected_height:
        return None
    return {
        "version": 1,
        "detection_known": False,
        "sheet": {"width": width, "height": height},
        "layout": layout,
        "entries": entries,
    }


def _audit_card_html(
        entry, index, layout, detection_known, scale,
        include_scripts=True):
    row = entry["row"]
    col = entry["col"]
    letter = entry["letter"]
    points = entry["points"]
    detection_mismatch = (
        detection_known
        and entry["detected"] != entry["transcribed"]
    )
    score_check = entry.get("score_check")
    letter_review = entry.get("letter_check") == "review"
    score_review = score_check == "review"
    score_attention = (
        entry["transcribed"]
        and score_check in {"review", "ambiguous", "unavailable"}
    )
    mismatch = detection_mismatch or letter_review or score_review
    classes = ["audit-card"]
    if entry["blank"]:
        classes.append("blank")
    if score_attention:
        classes.append("score")
    if letter_review:
        classes.append("letter")
    if mismatch:
        classes.append("mismatch")

    if detection_mismatch and letter_review and score_review:
        state = "Review tile, letter, and score"
    elif detection_mismatch and letter_review:
        state = "Review tile and letter"
    elif letter_review and score_review:
        state = "Review letter and score"
    elif detection_mismatch and score_review:
        state = "Review tile and score"
    elif letter_review:
        state = "Review letter"
    elif score_review:
        state = "Review score"
    elif detection_mismatch:
        state = "Review mismatch"
    elif score_attention:
        state = "Verify score"
    elif entry["blank"]:
        state = "Blank - 0 pts"
    elif entry["transcribed"]:
        suffix = "pt" if points == 1 else "pts"
        state = f"{letter} - {points} {suffix}"
    else:
        state = "Missing from JSON"

    if not entry["transcribed"]:
        claim = "JSON is missing this detected source tile."
    elif entry["blank"]:
        claim = (
            f'JSON: <code>{escape(letter.lower())}</code> '
            "(blank, 0 pts)"
        )
    else:
        suffix = "pt" if points == 1 else "pts"
        claim = (
            f'JSON: <code>{escape(letter.upper())}</code> '
            f"({points} {suffix})"
        )
    if (
            detection_known
            and not entry["detected"]
            and entry["transcribed"]):
        claim += " Source detection missed this coordinate."
    if score_attention:
        claim += (
            f'<span class="audit-score-note {score_check}">'
            f'{escape(entry["score_reason"])}</span>'
        )
    if letter_review:
        claim += (
            '<span class="audit-letter-note review">'
            f'{escape(entry["letter_reason"])}</span>'
        )

    card_row, card_col = divmod(index, layout["columns"])
    card_x = card_col * layout["card_width"]
    card_y = (
        layout["page_header_height"] + card_row * layout["card_height"]
    )
    image_y = card_y + layout["image_top"]
    whole_x = card_x + layout["whole_left"]
    score_x = card_x + layout["score_left"]
    scaled_image_y = int(round(image_y * scale))
    scaled_whole_x = int(round(whole_x * scale))
    scaled_score_x = int(round(score_x * scale))
    coordinate = f"Row {row}, column {col}"
    if entry["transcribed"]:
        kind = "blank tile" if entry["blank"] else "tile"
        label = (
            f'aria-label="Return to {kind} '
            f'{escape(letter)} at row {row}, column {col} on the board"'
        )
        if include_scripts:
            # Scripted output avoids fragment links so embedded viewers never
            # treat a same-page jump as external navigation.
            opening = (
                f'<div id="audit-{row}-{col}" class="{" ".join(classes)}" '
                f'role="button" tabindex="0" '
                f'data-board-target="board-cell-{row}-{col}" {label}>'
            )
            closing = "</div>"
        else:
            opening = (
                f'<a id="audit-{row}-{col}" class="{" ".join(classes)}" '
                f'href="#board-cell-{row}-{col}" {label}>'
            )
            closing = "</a>"
    else:
        opening = (
            f'<article id="audit-{row}-{col}" '
            f'class="{" ".join(classes)}" tabindex="-1">'
        )
        closing = "</article>"
    return (
        opening
        + '<div class="audit-card-top">'
        f'<span class="audit-coordinate">({row},{col})</span>'
        f'<span class="audit-state">{escape(state)}</span></div>'
        '<div class="audit-comparison">'
        '<figure class="audit-figure">'
        f'<div class="audit-crop" role="img" aria-label="Full source tile at '
        f'{escape(coordinate)}" style="background-position:'
        f'-{scaled_whole_x}px -{scaled_image_y}px"></div>'
        '<figcaption>Source tile</figcaption></figure>'
        '<figure class="audit-figure">'
        f'<div class="audit-crop" role="img" aria-label="Enlarged score '
        f'corner at {escape(coordinate)}" style="background-position:'
        f'-{scaled_score_x}px -{scaled_image_y}px"></div>'
        '<figcaption>Score corner</figcaption></figure></div>'
        f'<p class="audit-claim">{claim}</p>{closing}'
    )


def _responsive_tile_audit_html(
        encoded, manifest, include_scripts=True):
    entries = manifest["entries"]
    layout = manifest["layout"]
    width = manifest["sheet"]["width"]
    height = manifest["sheet"]["height"]
    blank_count = sum(entry["blank"] for entry in entries)
    detection_known = manifest["detection_known"]
    score_metadata_known = any("score_check" in entry for entry in entries)
    letter_metadata_known = any(
        "letter_check" in entry
        for entry in entries
    )
    mismatch_count = sum(
        (
            detection_known
            and entry["detected"] != entry["transcribed"]
        )
        or entry.get("letter_check") == "review"
        or entry.get("score_check") == "review"
        for entry in entries
    ) if (
        detection_known or score_metadata_known or letter_metadata_known
    ) else None
    score_check_count = sum(
        entry["transcribed"]
        and entry.get("score_check") in {
            "review", "ambiguous", "unavailable"
        }
        for entry in entries
    )
    score_review_count = sum(
        entry.get("score_check") == "review"
        for entry in entries
    )
    letter_review_count = sum(
        entry.get("letter_check") == "review"
        for entry in entries
    )
    scale = 0.45
    crop_size = max(1, int(round(layout["image_size"] * scale)))
    cards = "".join(
        _audit_card_html(
            entry,
            index,
            layout,
            detection_known,
            scale,
            include_scripts=include_scripts,
        )
        for index, entry in enumerate(entries)
    )
    if not cards:
        cards = (
            '<p class="audit-empty">No detected or transcribed tiles.</p>'
        )
    tile_word = "tile" if len(entries) == 1 else "tiles"
    blank_word = "blank" if blank_count == 1 else "blanks"

    def filter_chip(filter_name, label, css_class=""):
        classes = f"audit-chip audit-filter {css_class}".strip()
        if include_scripts:
            pressed = "true" if filter_name == "all" else "false"
            return (
                f'<button type="button" class="{classes}" '
                f'data-audit-filter="{filter_name}" '
                'aria-controls="source-audit-grid" '
                f'aria-pressed="{pressed}">{label}</button>'
            )
        return f'<span class="audit-chip {css_class}">{label}</span>'

    tile_chip = filter_chip(
        "all",
        f"{len(entries)} {tile_word}",
    )
    blank_chip = filter_chip(
        "blank",
        f"{blank_count} {blank_word}",
        "blank",
    )
    if mismatch_count is None:
        detection_chip = (
            '<span class="audit-chip">Detection status unavailable</span>'
        )
    else:
        mismatch_word = "mismatch" if mismatch_count == 1 else "mismatches"
        mismatch_class = "ok" if mismatch_count == 0 else "alert"
        detection_chip = filter_chip(
            "mismatch",
            f"{mismatch_count} {mismatch_word}",
            mismatch_class,
        )
    if score_metadata_known:
        score_word = "check" if score_check_count == 1 else "checks"
        score_class = (
            "alert"
            if score_review_count
            else "blank" if score_check_count else "ok"
        )
        score_chip = filter_chip(
            "score",
            f"{score_check_count} score {score_word}",
            score_class,
        )
    else:
        score_chip = ""
    if letter_metadata_known:
        letter_word = (
            "review" if letter_review_count == 1 else "reviews"
        )
        letter_class = "alert" if letter_review_count else "ok"
        letter_chip = filter_chip(
            "letter",
            f"{letter_review_count} letter {letter_word}",
            letter_class,
        )
    else:
        letter_chip = ""
    scaled_width = int(round(width * scale))
    scaled_height = int(round(height * scale))
    filter_feedback = (
        '<p class="audit-filter-empty" hidden>'
        "No audit tiles match this category.</p>"
        '<span class="audit-filter-status" role="status" '
        'aria-live="polite"></span>'
    ) if include_scripts else ""
    return (
        '<section class="tile-audit-panel" '
        'aria-labelledby="source-tile-audit">'
        '<div class="audit-section-header"><div class="audit-heading">'
        '<div class="audit-kicker">Source verification</div>'
        '<h2 id="source-tile-audit">Tile and score audit</h2>'
        '<p class="audit-intro">Compare each source tile with its enlarged '
        'score corner and JSON claim. Every displayed 0 must be a lowercase '
        'blank in JSON, and every lowercase blank must display 0. A Tesseract '
        'reading is the preferred correction when it conflicts with JSON; the '
        'built-in shape check only flags. Visually verify every ambiguous or '
        'unavailable reading.</p></div>'
        '<div class="audit-summary">'
        f"{tile_chip}{blank_chip}"
        f"{detection_chip}{letter_chip}{score_chip}</div></div>"
        f'<div id="source-audit-grid" class="audit-grid" '
        f'style="--audit-sheet:url('
        f"'data:image/png;base64,{encoded}');"
        f'--audit-sheet-width:{scaled_width}px;'
        f'--audit-sheet-height:{scaled_height}px;'
        f'--audit-crop-size:{crop_size}px">{cards}'
        f"{filter_feedback}</div></section>"
    )


def _tile_audit_content(image_path, board, include_scripts=True):
    image_path = Path(image_path)
    mime_types = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
    }
    mime_type = mime_types.get(image_path.suffix.lower())
    if mime_type is None:
        raise ValueError("Tile audit image must be PNG or JPEG")
    image_bytes = image_path.read_bytes()
    if not image_bytes:
        raise ValueError(f"Tile audit image is empty: {image_path}")
    encoded = base64.b64encode(image_bytes).decode("ascii")
    if mime_type == "image/png":
        width, height, text_chunks = _png_info(image_bytes)
        manifest_json = text_chunks.get(AUDIT_METADATA_KEY)
        if manifest_json is not None:
            try:
                manifest = json.loads(manifest_json)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    "Tile audit PNG has invalid responsive metadata"
                ) from exc
            manifest = _validate_audit_manifest(manifest, width, height)
        else:
            manifest = _legacy_audit_manifest(board, width, height)
        if manifest is not None:
            targets = {
                (entry["row"], entry["col"])
                for entry in manifest["entries"]
                if entry["transcribed"]
            }
            alerts = {
                (entry["row"], entry["col"])
                for entry in manifest["entries"]
                if entry["transcribed"]
                and "review" in (
                    entry.get("letter_check"),
                    entry.get("score_check"),
                )
            }
            return (
                _responsive_tile_audit_html(
                    encoded,
                    manifest,
                    include_scripts=include_scripts,
                ),
                targets,
                alerts,
            )

    return (
        '<section class="tile-audit-panel" '
        'aria-labelledby="source-tile-audit">'
        '<div class="audit-section-header"><div class="audit-heading">'
        '<div class="audit-kicker">Source verification</div>'
        '<h2 id="source-tile-audit">Tile and score audit</h2>'
        '<p class="audit-intro">Compare each source tile and score corner '
        'with the board transcription.</p></div></div>'
        '<div class="tile-audit-image-wrap">'
        f'<img class="tile-audit-image" src="data:{mime_type};base64,{encoded}" '
        'alt="Source tiles and enlarged score corners for board verification">'
        "</div></section>",
        set(),
        set(),
    )


def _tile_audit_html(image_path, board, include_scripts=True):
    html, _, _ = _tile_audit_content(
        image_path,
        board,
        include_scripts=include_scripts,
    )
    return html


def _write_html(parts, output_path, message):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(parts), encoding="utf-8")
    print(f"{message}: {output_path}")


def generate_board_confirm_html(
        board, premium, output_path, title="Board Confirmation", subtitle="",
        include_scripts=True, tile_audit_path=None):
    """Generate a board-confirmation page with an optional embedded tile audit."""
    board = _norm_str_keys(board)
    premium = _norm_premium(premium)
    audit_html = None
    audit_targets = set()
    audit_alerts = set()
    if tile_audit_path is not None:
        audit_html, audit_targets, audit_alerts = _tile_audit_content(
            tile_audit_path,
            board,
            include_scripts=include_scripts,
        )
    parts = [CSS, COPY_CSS]
    if include_scripts:
        parts.append(THEME_SCRIPT)
        parts.append(BOARD_COPY_SCRIPT)
        parts.append(AUDIT_SCRIPT)
    parts.append('<div class="page">')
    parts.append(f'<h1>{escape(str(title))}</h1>')
    if subtitle:
        parts.append(f'<div class="subtitle">{escape(str(subtitle))}</div>')
    parts.append(blank_audit_html(board))
    parts.append('<div data-board-export>')
    if include_scripts:
        parts.append(
            '<div class="board-toolbar">'
            f'{_theme_actions_html()}{_copy_actions_html()}</div>'
        )
    parts.append('<div class="board"><div class="cell hdr"></div>')
    for c in range(15):
        parts.append(f'<div class="cell hdr">{c}</div>')
    for r in range(15):
        parts.append(f'<div class="cell hdr">{r}</div>')
        for c in range(15):
            parts.append(
                cell_html(
                    r,
                    c,
                    board,
                    {},
                    premium,
                    audit_targets=audit_targets,
                    include_scripts=include_scripts,
                    audit_alerts=audit_alerts,
                )
            )
    parts.append('</div></div>')
    occupied = _occupied_coordinates(board)
    legend_entries = []
    if board:
        legend_entries.append(
            '<div class="leg"><span class="leg-box" '
            'style="background:var(--tile)"></span> Tile</div>'
        )
    if _has_blank(board):
        legend_entries.append(
            '<div class="leg"><span class="leg-box blank-swatch">'
            '<span class="blank-swatch-mark">B</span>0</span> '
            'Blank (0 points)</div>'
        )
    if audit_alerts:
        legend_entries.append(
            '<div class="leg"><span class="leg-box alert-swatch">'
            '<span class="alert-swatch-mark">!</span></span> '
            'Needs review</div>'
        )
    legend_entries.extend(
        _legend_prem_html(_visible_premium_types(premium, occupied))
    )
    parts.append(_legend_html(legend_entries))
    if audit_html is not None:
        parts.append(audit_html)
    parts.append('</div>')
    _write_html(parts, output_path, "Board confirmation written to")


def generate_moves_html(
        title, subtitle, board, premium, moves, output_path,
        include_scripts=True):
    """Generate full HTML page with move boards."""
    board = _norm_str_keys(board)
    premium = _norm_premium(premium)

    parts = [CSS, COPY_CSS, MOVES_RESULT_CSS]
    if include_scripts:
        parts.append(THEME_SCRIPT)
        parts.append(BOARD_COPY_SCRIPT)

    parts.append('<div class="page">')
    parts.append(f'<h1>{escape(str(title))}</h1>')
    parts.append(f'<div class="subtitle">{escape(str(subtitle))}</div>')
    if include_scripts:
        parts.append(
            f'<div class="board-toolbar">{_theme_actions_html()}</div>'
        )
    move_tiles = [move["tiles"] for move in moves]
    legend_entries = []
    if board:
        legend_entries.append(
            '<div class="leg"><span class="leg-box" '
            'style="background:var(--tile)"></span> Existing</div>'
        )
    if any(move_tiles):
        legend_entries.append(
            '<div class="leg"><span class="leg-box" '
            'style="background:var(--new-tile);'
            'box-shadow:inset 0 0 0 2px var(--new-border)"></span> '
            'Play here</div>'
        )
    if _has_blank(board, *move_tiles):
        legend_entries.append(
            '<div class="leg"><span class="leg-box blank-swatch">B0</span> '
            'Blank (0 points)</div>'
        )
    # A premium stays in the legend while any rendered move board still shows it.
    visible_premiums = set()
    for tiles in move_tiles:
        visible_premiums |= _visible_premium_types(
            premium,
            _occupied_coordinates(board, tiles),
        )
    legend_entries.extend(_legend_prem_html(visible_premiums))
    parts.append(_legend_html(legend_entries))

    for i, move in enumerate(moves):
        parts.append('<div class="move-section" data-board-export>')
        word = escape(str(move["word"]))
        points = escape(str(move["pts"]))
        direction = escape(str(move["dir"]))
        cross_words = escape(str(move["cross"]))
        note = escape(str(move["note"]))
        copy_actions = _copy_actions_html() if include_scripts else ""
        parts.append(
            f'<div class="move-header"><span class="move-title">'
            f'#{i+1}: <strong>{word}</strong> -- {points} pts'
            f'</span>{copy_actions}</div>'
        )
        parts.append('<div class="board"><div class="cell hdr"></div>')
        for c in range(15):
            parts.append(f'<div class="cell hdr">{c}</div>')
        for r in range(15):
            parts.append(f'<div class="cell hdr">{r}</div>')
            for c in range(15):
                parts.append(
                    cell_html(
                        r,
                        c,
                        board,
                        move["tiles"],
                        premium,
                        show_blank_mark=False,
                    )
                )
        parts.append('</div>')
        parts.append(
            '<div class="move-info">'
            f'<span><strong>Placement:</strong> {direction}</span>'
            f'<span><strong>Cross-words:</strong> {cross_words}</span>'
            "</div>"
        )
        parts.append(f'<div class="move-note">{note}</div>')
        parts.append('</div>')

    parts.append('</div>')
    _write_html(parts, output_path, f"Written {len(moves)} moves to")


def _read_json(path):
    with Path(path).open("r", encoding="utf-8") as f:
        return json.load(f)


def _load_board(path):
    data = _read_json(path)
    return normalize_board_tiles(data)


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
        if (
                not isinstance(move["word"], str)
                or not move["word"]
                or not move["word"].isascii()
                or not move["word"].isalpha()
                or not move["word"].isupper()):
            raise ValueError(f"Move {index} 'word' must contain A-Z letters")
        if type(move["pts"]) is not int or move["pts"] < 0:
            raise ValueError(f"Move {index} 'pts' must be a non-negative integer")
        for field in ("dir", "cross", "note"):
            if not isinstance(move[field], str):
                raise ValueError(f"Move {index} '{field}' must be a string")
        try:
            move["tiles"] = normalize_board_tiles(move["tiles"])
        except ValueError as exc:
            raise ValueError(f"Move {index} has invalid tiles: {exc}") from exc
    return moves


def _add_common_arguments(parser, default_title):
    parser.add_argument("--board", required=True, help="Path to board JSON")
    parser.add_argument("--output", required=True, help="Output HTML path")
    parser.add_argument("--title", default=default_title)
    parser.add_argument("--subtitle", default="")
    parser.add_argument(
        "--no-script",
        action="store_true",
        help="Omit JavaScript and board copy controls",
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description="Render Crossplay board HTML")
    subparsers = parser.add_subparsers(dest="command", required=True)

    board_parser = subparsers.add_parser(
        "board", help="Render a board-confirmation page"
    )
    _add_common_arguments(board_parser, "Board Confirmation")
    board_parser.add_argument(
        "--tile-audit",
        help="Path to a PNG or JPEG tile audit to embed in the HTML",
    )

    moves_parser = subparsers.add_parser(
        "moves", help="Render move recommendations"
    )
    _add_common_arguments(moves_parser, "Crossplay Moves")
    moves_parser.add_argument("--moves", required=True, help="Path to moves JSON")

    args = parser.parse_args(argv)
    try:
        board = _load_board(args.board)
    except (OSError, ValueError) as exc:
        parser.error(f"could not load board: {exc}")
    if args.command == "board":
        try:
            generate_board_confirm_html(
                board,
                DEFAULT_PREMIUM,
                args.output,
                title=args.title,
                subtitle=args.subtitle,
                include_scripts=not args.no_script,
                tile_audit_path=args.tile_audit,
            )
        except (OSError, ValueError) as exc:
            parser.error(f"could not render board: {exc}")
        return

    try:
        moves = _load_moves(args.moves)
    except (OSError, ValueError) as exc:
        parser.error(f"could not load moves: {exc}")
    generate_moves_html(
        args.title,
        args.subtitle,
        board,
        DEFAULT_PREMIUM,
        moves,
        args.output,
        include_scripts=not args.no_script,
    )


if __name__ == "__main__":
    main()
