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
    --audit-ok-bg: #20351c;
  }
}

body{font-family:system-ui,-apple-system,sans-serif;padding:16px;background:var(--bg);color:var(--text)}
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
.cell.new{background:var(--new-tile);color:#fff;border-radius:2px;box-shadow:inset 0 0 0 2px var(--new-border)}
.cell.new.blank{background:var(--new-tile-blank,#f0a866);box-shadow:inset 0 0 0 2px var(--blank-border)}
.cell.star{background:var(--hdr-bg);font-size:13px;color:var(--star)}
.cell.empty{background:var(--cell-bg)}
.cell.prem{background:var(--prem-light-bg);color:var(--prem-light-fg);font-size:8px;font-weight:500}
.pts{position:absolute;top:2px;right:2px;font-size:8px;line-height:1;opacity:.9;font-weight:650}
.cell.blank .pts{font-size:9px;opacity:1;font-weight:800;color:#fff}
.blank-mark{position:absolute;bottom:2px;left:2px;font-size:7px;line-height:1;font-weight:800;color:var(--blank-border)}
.cell.audit-link{cursor:pointer;text-decoration:none}
.cell.audit-link:hover,.cell.audit-link:focus-visible{z-index:1;outline:2px solid var(--divider);outline-offset:-2px}
.cell.audit-link:target{z-index:2;outline:3px solid var(--audit-accent);outline-offset:-3px}
.blank-audit{max-width:540px;margin:0 0 12px;padding:10px 12px;border:2px solid var(--blank-audit-border);border-radius:6px;background:var(--blank-audit-bg);font-size:13px;line-height:1.45}
.blank-swatch{background:var(--tile-blank);box-shadow:inset 0 0 0 2px var(--blank-border);color:#fff;font-size:7px;font-weight:800;text-align:center;line-height:16px}
.legend{display:flex;gap:16px;margin:12px 0 24px;font-size:12px;color:var(--text-sec);flex-wrap:wrap}
.leg{display:flex;align-items:center;gap:4px}
.leg-box{width:16px;height:16px;border-radius:3px;display:inline-block}
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
.audit-card{display:block;min-width:0;padding:9px;border:1px solid var(--surface-border);border-radius:10px;background:var(--surface);box-shadow:var(--surface-shadow);color:inherit;text-decoration:none;cursor:pointer;scroll-margin-top:16px}
.audit-card.blank{border-color:var(--audit-blank)}
.audit-card.mismatch{border-color:var(--audit-alert);box-shadow:inset 0 3px 0 var(--audit-alert)}
.audit-card:hover{border-color:var(--audit-accent)}
.audit-card:focus-visible{outline:2px solid var(--audit-accent);outline-offset:2px}
.audit-card:target{outline:3px solid var(--divider);outline-offset:2px}
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
.audit-empty,.audit-filter-empty{grid-column:1/-1;padding:24px;color:var(--text-sec);font-size:13px;text-align:center}
.audit-filter-status{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}
.tile-audit-image-wrap{padding:12px;border:1px solid var(--surface-border);border-top:0;border-radius:0 0 12px 12px;background:var(--surface-subtle);overflow:auto}
.tile-audit-image{display:block;max-width:100%;height:auto;margin:auto;border:1px solid var(--surface-border);border-radius:8px;background:#fff}
@media (max-width:620px){
  body{padding:12px}
  .audit-section-header{display:block;padding:14px}
  .audit-heading{min-width:0}
  .audit-summary{justify-content:flex-start;margin-top:12px}
  .audit-grid{grid-template-columns:1fr;padding:10px}
}
@media (prefers-color-scheme:dark){.cell.prem{background:var(--prem-dark-bg);color:var(--prem-dark-fg)}}
</style>"""

COPY_CSS = """<style>
.board-toolbar{display:flex;justify-content:flex-end;max-width:540px;margin-bottom:4px}
.copy-actions{display:flex;align-items:center;gap:4px;margin-left:auto}
.copy-btn{border:1px solid var(--grid-border);border-radius:4px;background:var(--hdr-bg);color:var(--text);padding:2px 6px;font:inherit;font-size:11px;cursor:pointer}
.copy-btn:hover{border-color:var(--divider)}
.copy-btn:focus-visible{outline:2px solid var(--divider);outline-offset:2px}
.copy-btn:disabled{cursor:wait;opacity:.6}
.copy-status{color:var(--text-sec);font-size:11px;font-weight:400}
.copy-status.error{color:#b42318}
@media (prefers-color-scheme:dark){.copy-status.error{color:#ff9b8f}}
@media print{.copy-actions{display:none}}
</style>"""

MOVES_RESULT_CSS = """<style>
.cell.tile.blank,.cell.new.blank{background:var(--tile-blank);box-shadow:none}
.cell.blank .pts,.blank-swatch{font-weight:400}
.blank-swatch{box-shadow:none}
.move-header{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}
.move-title{min-width:0}
.move-section .cell.tile,.move-section .cell.new{cursor:default}
.move-section .cell.tile:hover,.move-section .cell.new:hover{z-index:1;outline:2px solid var(--divider);outline-offset:-2px}
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
  let clipboardError = null;
  if (navigator.clipboard && window.ClipboardItem) {
    const svgType = 'image/svg+xml';
    const supportsSvg = typeof ClipboardItem.supports !== 'function'
      || ClipboardItem.supports(svgType);
    if (supportsSvg) {
      const item = new ClipboardItem({
        [svgType]: new Blob([svg], {type: svgType}),
        'text/plain': new Blob([svg], {type: 'text/plain'})
      });
      try {
        await navigator.clipboard.write([item]);
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

async function boardPngBlob(board) {
  const rect = board.getBoundingClientRect();
  const width = Math.ceil(rect.width);
  const height = Math.ceil(rect.height);
  const svg = boardSvgMarkup(board);
  const url = URL.createObjectURL(
    new Blob([svg], {type: 'image/svg+xml;charset=utf-8'})
  );
  try {
    const image = await loadImage(url);
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
    URL.revokeObjectURL(url);
  }
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
  if (!['all', 'blank', 'mismatch'].includes(filter)) {
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

function revealAuditTarget(link) {
  const targetId = link.hash.slice(1);
  const target = document.getElementById(targetId);
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
}

function revealBoardTarget(link) {
  const targetId = link.hash.slice(1);
  const target = document.getElementById(targetId);
  const board = target && target.closest('.board');
  if (!target || !board) {
    return;
  }
  window.location.hash = link.hash;
  target.focus({preventScroll: true});
  const behavior = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    ? 'auto'
    : 'smooth';
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
  const auditLink = event.target.closest('.audit-link[href^="#audit-"]');
  if (auditLink) {
    revealAuditTarget(auditLink);
    return;
  }
  const boardLink = event.target.closest(
    '.audit-card[href^="#board-cell-"]'
  );
  if (boardLink) {
    event.preventDefault();
    revealBoardTarget(boardLink);
  }
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
        show_blank_mark=True):
    letter = raw.upper()
    is_blank = raw.islower()
    pts = 0 if is_blank else TILE_PTS.get(letter, 0)
    blank_mark = (
        '<span class="blank-mark">B</span>'
        if is_blank and show_blank_mark
        else ""
    )
    tag = "div"
    attributes = f'class="{cell_class}"'
    if link_to_audit:
        tag = "a"
        kind = "blank tile" if is_blank else "tile"
        attributes = (
            f'id="board-cell-{r}-{c}" class="{cell_class} audit-link" '
            f'href="#audit-{r}-{c}" '
            f'aria-label="View source audit for {kind} '
            f'{escape(letter)} at row {r}, column {c}"'
        )
    return (
        f"<{tag} {attributes}>{blank_mark}{escape(letter)}"
        f'<span class="pts">{pts}</span></{tag}>'
    )


def cell_html(
        r, c, board, new_tiles, premium, audit_targets=None,
        show_blank_mark=True):
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
        if points is not None and (type(points) is not int or points < 0):
            raise ValueError("Tile audit PNG entry has invalid points")
        if entry["blank"] and not entry["transcribed"]:
            raise ValueError("Untranscribed tile audit entry cannot be blank")
        if entry["transcribed"] and points is None:
            raise ValueError("Transcribed tile audit entry is missing points")
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


def _audit_card_html(entry, index, layout, detection_known, scale):
    row = entry["row"]
    col = entry["col"]
    letter = entry["letter"]
    points = entry["points"]
    mismatch = (
        detection_known
        and entry["detected"] != entry["transcribed"]
    )
    classes = ["audit-card"]
    if entry["blank"]:
        classes.append("blank")
    if mismatch:
        classes.append("mismatch")

    if mismatch:
        state = "Review mismatch"
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
    kind = "blank tile" if entry["blank"] else "tile"
    return (
        f'<a id="audit-{row}-{col}" class="{" ".join(classes)}" '
        f'href="#board-cell-{row}-{col}" aria-label="Return to {kind} '
        f'{escape(letter)} at row {row}, column {col} on the board">'
        '<div class="audit-card-top">'
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
        f'<p class="audit-claim">{claim}</p></a>'
    )


def _responsive_tile_audit_html(
        encoded, manifest, include_scripts=True):
    entries = manifest["entries"]
    layout = manifest["layout"]
    width = manifest["sheet"]["width"]
    height = manifest["sheet"]["height"]
    blank_count = sum(entry["blank"] for entry in entries)
    detection_known = manifest["detection_known"]
    mismatch_count = sum(
        entry["detected"] != entry["transcribed"] for entry in entries
    ) if detection_known else None
    scale = 0.45
    crop_size = max(1, int(round(layout["image_size"] * scale)))
    cards = "".join(
        _audit_card_html(
            entry,
            index,
            layout,
            detection_known,
            scale,
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
        'blank in JSON, and every lowercase blank must display 0.</p></div>'
        '<div class="audit-summary">'
        f"{tile_chip}{blank_chip}"
        f"{detection_chip}</div></div>"
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
            return (
                _responsive_tile_audit_html(
                    encoded,
                    manifest,
                    include_scripts=include_scripts,
                ),
                targets,
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
    )


def _tile_audit_html(image_path, board, include_scripts=True):
    html, _ = _tile_audit_content(
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
    if tile_audit_path is not None:
        audit_html, audit_targets = _tile_audit_content(
            tile_audit_path,
            board,
            include_scripts=include_scripts,
        )
    parts = [CSS, COPY_CSS]
    if include_scripts:
        parts.append(BOARD_COPY_SCRIPT)
        parts.append(AUDIT_SCRIPT)
    parts.append(f'<h1>{escape(str(title))}</h1>')
    if subtitle:
        parts.append(f'<div class="subtitle">{escape(str(subtitle))}</div>')
    parts.append(blank_audit_html(board))
    parts.append('<div data-board-export>')
    if include_scripts:
        parts.append(f'<div class="board-toolbar">{_copy_actions_html()}</div>')
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
                )
            )
    parts.append('</div></div>')
    parts.append("""<div class="legend">
  <div class="leg"><span class="leg-box" style="background:var(--tile)"></span> Tile</div>
  <div class="leg"><span class="leg-box blank-swatch">B0</span> Blank (0 points)</div>
  <div class="leg"><span class="leg-box" style="background:#FAECE7;border:1px solid #ddd;font-size:8px;display:flex;align-items:center;justify-content:center;color:#993C1D">3W</span> Triple Word</div>
  <div class="leg"><span class="leg-box" style="background:#FBEAF0;border:1px solid #ddd;font-size:8px;display:flex;align-items:center;justify-content:center;color:#993556">2W</span> Double Word</div>
  <div class="leg"><span class="leg-box" style="background:#E6F1FB;border:1px solid #ddd;font-size:8px;display:flex;align-items:center;justify-content:center;color:#185FA5">3L</span> Triple Letter</div>
  <div class="leg"><span class="leg-box" style="background:#EAF3DE;border:1px solid #ddd;font-size:8px;display:flex;align-items:center;justify-content:center;color:#3B6D11">2L</span> Double Letter</div>
</div>""")
    if audit_html is not None:
        parts.append(audit_html)
    _write_html(parts, output_path, "Board confirmation written to")


def generate_moves_html(
        title, subtitle, board, premium, moves, output_path,
        include_scripts=True):
    """Generate full HTML page with move boards."""
    board = _norm_str_keys(board)
    premium = _norm_premium(premium)

    parts = [CSS, COPY_CSS, MOVES_RESULT_CSS]
    if include_scripts:
        parts.append(BOARD_COPY_SCRIPT)

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
