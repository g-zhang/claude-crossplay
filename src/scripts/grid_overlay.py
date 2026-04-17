#!/usr/bin/env python3
"""
Crossplay grid overlay tool — robust anchor detection.

Detects the 15x15 board by finding premium-square clusters on ALL FOUR edges
(left/right for rows, top/bottom for columns), matching clusters across
opposite edges (so UI elements like the avatar or tile rack that only appear
on one side get filtered out), then fitting a linear grid model to the known
Crossplay premium pattern at positions {0, 3, 7, 11, 14}.

The fit produces a max-pixel residual vs predicted grid positions, which is
used to flag/reject bad detections. Finally we cross-check that cell_x ≈
cell_y (the board must be square); if they disagree we use whichever axis
had the lower residual for both dimensions.
"""

import cv2
import numpy as np
import sys
from itertools import combinations
from pathlib import Path


# Crossplay premium-square rows/cols on the 4 edges — 3L at 0&14, 3W at 3&11, 2L at 7.
# Any real row/col anchor we detect should land on one of these positions.
PREMIUM_AXIS = (0, 3, 7, 11, 14)


def find_clusters(profile, min_sat=20, min_gap=5, min_width=3):
    """Find runs of high-saturation pixels in a 1D profile.
    Returns list of (center, start, end) tuples."""
    above = np.where(profile > min_sat)[0]
    if len(above) == 0:
        return []
    clusters = []
    start = above[0]
    prev = above[0]
    for idx in above[1:]:
        if idx - prev > min_gap:
            if prev - start + 1 >= min_width:
                clusters.append((int((start + prev) / 2), int(start), int(prev)))
            start = idx
        prev = idx
    if prev - start + 1 >= min_width:
        clusters.append((int((start + prev) / 2), int(start), int(prev)))
    return clusters


def match_opposite_edges(cl_a, cl_b, tol):
    """Match clusters across opposite edges (left/right or top/bottom) by
    center-coordinate proximity. Unmatched clusters are discarded as UI noise.

    Returns sorted list of averaged center coordinates."""
    matched = []
    used_b = set()
    for ca in cl_a:
        best_bi, best_diff = None, tol + 1
        for bi, cb in enumerate(cl_b):
            if bi in used_b:
                continue
            d = abs(ca[0] - cb[0])
            if d < best_diff:
                best_diff, best_bi = d, bi
        if best_bi is not None:
            matched.append((ca[0] + cl_b[best_bi][0]) // 2)
            used_b.add(best_bi)
    return sorted(matched)


def fit_grid_axis(anchors, expected=PREMIUM_AXIS):
    """Fit a 15-cell grid model to matched anchor centers.

    Robust to noise: if we have MORE anchors than expected premiums (e.g.
    the tile rack bleeds through), tries every size-len(expected) subset of
    anchors and picks the fit with the smallest residual. If we have FEWER,
    tries every subset of `expected` positions instead.

    Returns (origin_of_cell_0_center, cell_size, max_residual_px).
    Returns (None, None, inf) if < 2 anchors or no valid fit found."""
    if len(anchors) < 2:
        return None, None, float('inf')

    ys_all = np.array(sorted(anchors), dtype=float)
    N_expected = len(expected)
    best = (None, None, float('inf'))

    if len(ys_all) <= N_expected:
        # Fewer anchors than expected premiums — try assigning them to all
        # possible position-subsets of the expected pattern.
        for subset in combinations(expected, len(ys_all)):
            rows = np.array(subset, dtype=float)
            if rows[-1] - rows[0] < 3:
                continue
            A = np.vstack([rows, np.ones(len(ys_all))]).T
            (cell, origin), *_ = np.linalg.lstsq(A, ys_all, rcond=None)
            if cell <= 0:
                continue
            predicted = origin + rows * cell
            residual = float(np.max(np.abs(ys_all - predicted)))
            if residual < best[2]:
                best = (origin, cell, residual)
    else:
        # More anchors than expected — some are UI noise (e.g. tile rack).
        # Try every N_expected-subset of detected anchors, fitting against the
        # full expected pattern; the correct subset has minimal residual.
        rows = np.array(expected, dtype=float)
        A = np.vstack([rows, np.ones(N_expected)]).T
        for idx_subset in combinations(range(len(ys_all)), N_expected):
            ys = ys_all[list(idx_subset)]
            (cell, origin), *_ = np.linalg.lstsq(A, ys, rcond=None)
            if cell <= 0:
                continue
            predicted = origin + rows * cell
            residual = float(np.max(np.abs(ys - predicted)))
            if residual < best[2]:
                best = (origin, cell, residual)
    return best


def find_board_region(image, verbose=True):
    """Locate the 15x15 board using dual-axis anchor matching across all 4 edges.

    Returns (bx, by, bw, bh, diag_dict)."""
    h, w = image.shape[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150)

    # --- Phase 1: rough horizontal extent from edge projection ---
    col_sums = np.sum(edges, axis=0)
    row_sums = np.sum(edges, axis=1)
    col_indices = np.where(col_sums > np.max(col_sums) * 0.15)[0]
    row_indices = np.where(row_sums > np.max(row_sums) * 0.15)[0]

    diag = {}

    if len(col_indices) < 10 or len(row_indices) < 10:
        side = int(w * 0.96)
        diag['note'] = 'phase1-default-fallback'
        return int(w * 0.02), int(h * 0.25), side, side, diag

    x1 = int(col_indices[0])
    x2 = int(col_indices[-1])
    board_w_est = x2 - x1

    # --- Phase 2: scan full image height for row anchors ---
    # No vertical cropping needed — cluster matching across opposite edges
    # filters out UI noise like avatars or tile racks that only appear on one side.
    crop = image[:, x1:x2]
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    ch, cw = crop.shape[:2]

    # Strip width ~1 cell (1/15 ≈ 6.67%); use 5.5% to stay inside the board edge.
    strip = max(8, int(cw * 0.055))

    # --- ROW anchors: match left-edge clusters with right-edge clusters ---
    left_sat = np.mean(hsv[:, :strip, 1], axis=1)
    right_sat = np.mean(hsv[:, -strip:, 1], axis=1)
    left_cl = find_clusters(left_sat)
    right_cl = find_clusters(right_sat)
    # Match tolerance: ~1/4 cell. Cell is ~cw/15 ≈ 78px, so ~20px tolerance.
    tol_px = max(15, int(cw * 0.025))
    matched_ys = match_opposite_edges(left_cl, right_cl, tol_px)
    origin_y, cell_y, resid_y = fit_grid_axis(matched_ys)

    diag['left_clusters'] = [c[0] for c in left_cl]
    diag['right_clusters'] = [c[0] for c in right_cl]
    diag['matched_ys'] = matched_ys
    diag['cell_y'] = cell_y
    diag['resid_y'] = resid_y

    # --- COL anchors: match top-edge clusters with bottom-edge clusters ---
    # Need rough y-range for top/bottom strips. Use row anchors if available.
    if origin_y is not None and cell_y is not None:
        top_y = origin_y
        bot_y = origin_y + 14 * cell_y
        ts1 = max(0, int(top_y - cell_y * 0.4))
        ts2 = min(ch, int(top_y + cell_y * 0.4))
        bs1 = max(0, int(bot_y - cell_y * 0.4))
        bs2 = min(ch, int(bot_y + cell_y * 0.4))
    else:
        # Fallback: use phase 1 row-indices extent
        y1_p1 = int(row_indices[0])
        y2_p1 = int(row_indices[-1])
        ts1, ts2 = y1_p1, min(ch, y1_p1 + 80)
        bs1, bs2 = max(0, y2_p1 - 80), y2_p1

    matched_xs, top_cl, bot_cl = [], [], []
    origin_x, cell_x, resid_x = None, None, float('inf')
    if ts2 > ts1 and bs2 > bs1:
        top_sat = np.mean(hsv[ts1:ts2, :, 1], axis=0)
        bot_sat = np.mean(hsv[bs1:bs2, :, 1], axis=0)
        top_cl = find_clusters(top_sat)
        bot_cl = find_clusters(bot_sat)
        matched_xs = match_opposite_edges(top_cl, bot_cl, tol_px)
        origin_x, cell_x, resid_x = fit_grid_axis(matched_xs)

    diag['top_clusters'] = [c[0] for c in top_cl]
    diag['bot_clusters'] = [c[0] for c in bot_cl]
    diag['matched_xs'] = matched_xs
    diag['cell_x'] = cell_x
    diag['resid_x'] = resid_x

    # --- Cross-validate: board is square, so cell_x should ≈ cell_y ---
    if cell_y is not None and cell_x is not None:
        disagreement = abs(cell_y - cell_x) / max(cell_y, cell_x)
        diag['axis_disagreement'] = disagreement
        if disagreement > 0.05:
            # Axes disagree >5% — trust the one with smaller residual.
            if resid_y <= resid_x:
                cell_x = cell_y
                diag['note'] = f'x-axis rejected (resid {resid_x:.1f} > {resid_y:.1f}px)'
            else:
                cell_y = cell_x
                diag['note'] = f'y-axis rejected (resid {resid_y:.1f} > {resid_x:.1f}px)'

    if cell_y is not None and origin_y is not None:
        grid_top = origin_y - cell_y / 2
        grid_h = int(round(cell_y * 15))
    else:
        grid_top = int(row_indices[0])
        grid_h = board_w_est
        diag.setdefault('note', 'y-axis fallback: edge indices')

    if cell_x is not None and origin_x is not None:
        grid_left = origin_x - cell_x / 2
        grid_w = int(round(cell_x * 15))
    else:
        grid_left = 0
        grid_w = board_w_est
        diag.setdefault('note', 'x-axis fallback: phase-1 x extent')

    abs_x1 = int(x1 + grid_left)
    abs_y1 = int(grid_top)

    if verbose:
        print(f"  Row anchors: L={len(left_cl)} R={len(right_cl)} "
              f"matched={len(matched_ys)} "
              + (f"cell_y={cell_y:.1f}px resid={resid_y:.1f}px" if cell_y else "NO FIT"))
        print(f"  Col anchors: T={len(top_cl)} B={len(bot_cl)} "
              f"matched={len(matched_xs)} "
              + (f"cell_x={cell_x:.1f}px resid={resid_x:.1f}px" if cell_x else "NO FIT"))
        if 'axis_disagreement' in diag:
            print(f"  Axis agreement: cell_y vs cell_x differ by "
                  f"{diag['axis_disagreement']*100:.1f}%")
        if 'note' in diag:
            print(f"  Note: {diag['note']}")

    return abs_x1, abs_y1, grid_w, grid_h, diag


def detect_tile_cells(board_crop, grid_size=15):
    """Return a 15x15 bool array: True where a blue tile is detected."""
    hsv = cv2.cvtColor(board_crop, cv2.COLOR_BGR2HSV)
    # Tuned for Crossplay blue tiles (H≈85-130, S≈55+, V≈80+).
    lower_blue = np.array([85, 55, 80])
    upper_blue = np.array([130, 255, 255])
    mask = cv2.inRange(hsv, lower_blue, upper_blue)

    bh, bw = board_crop.shape[:2]
    cell_h, cell_w = bh / grid_size, bw / grid_size

    tiles = [[False] * grid_size for _ in range(grid_size)]
    for r in range(grid_size):
        for c in range(grid_size):
            y1 = int(r * cell_h)
            y2 = int((r + 1) * cell_h)
            x1 = int(c * cell_w)
            x2 = int((c + 1) * cell_w)
            cell_mask = mask[y1:y2, x1:x2]
            ratio = np.sum(cell_mask > 0) / max(1, cell_mask.size)
            tiles[r][c] = ratio > 0.42
    return tiles


def draw_grid_overlay(image, bx, by, bw, bh, tiles, grid_size=15):
    """Draw numbered grid lines and tile highlights on a copy of the image."""
    pad_left = 0
    if bx < 40:
        pad_left = 40 - bx
        out = cv2.copyMakeBorder(image, 0, 0, pad_left, 0, cv2.BORDER_CONSTANT, value=(255, 255, 255))
        bx += pad_left
    else:
        out = image.copy()
    cell_w = bw / grid_size
    cell_h = bh / grid_size

    for r in range(grid_size):
        for c in range(grid_size):
            if tiles[r][c]:
                x1 = int(bx + c * cell_w) + 2
                y1 = int(by + r * cell_h) + 2
                x2 = int(bx + (c + 1) * cell_w) - 2
                y2 = int(by + (r + 1) * cell_h) - 2
                cv2.rectangle(out, (x1, y1), (x2, y2), (0, 220, 0), 2)

    for i in range(grid_size + 1):
        x = int(bx + i * cell_w)
        cv2.line(out, (x, int(by)), (x, int(by + bh)), (0, 0, 200), 1)
        y = int(by + i * cell_h)
        cv2.line(out, (int(bx), y), (int(bx + bw), y), (0, 0, 200), 1)

    font = cv2.FONT_HERSHEY_SIMPLEX
    fs = 0.55
    ft = 2
    cv2.rectangle(out, (int(bx) - 2, int(by) - 28), (int(bx + bw) + 2, int(by) - 1), (255, 255, 255), -1)
    for c in range(grid_size):
        cx = int(bx + (c + 0.35) * cell_w)
        cv2.putText(out, str(c), (cx, int(by) - 8), font, fs, (200, 0, 0), ft)

    cv2.rectangle(out, (int(bx) - 32, int(by)), (int(bx) - 1, int(by + bh)), (255, 255, 255), -1)
    for r in range(grid_size):
        ry = int(by + (r + 0.65) * cell_h)
        cv2.putText(out, str(r), (int(bx) - 30, ry), font, fs, (200, 0, 0), ft)

    return out


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Crossplay grid overlay")
    parser.add_argument("image", help="Path to screenshot")
    parser.add_argument("-o", "--output", default="/home/claude/grid_overlay.png")
    parser.add_argument("--debug", action="store_true", help="Print full diagnostic info")
    args = parser.parse_args()

    image = cv2.imread(str(args.image))
    if image is None:
        print(f"Error: Could not read {args.image}", file=sys.stderr)
        sys.exit(1)

    print(f"Image: {image.shape[1]}x{image.shape[0]}")

    bx, by, bw, bh, diag = find_board_region(image, verbose=True)
    print(f"Board: x={bx} y={by} w={bw} h={bh}, cell={bw/15:.1f}x{bh/15:.1f}px")

    if args.debug:
        print("\nDiagnostics:")
        for k, v in diag.items():
            print(f"  {k}: {v}")

    board_crop = image[by:by+bh, bx:bx+bw]
    tiles = detect_tile_cells(board_crop)

    tile_count = sum(sum(row) for row in tiles)
    print(f"Tiles detected: {tile_count}")

    print("\nTile map (X=tile):")
    print("   " + " ".join(f"{c:2d}" for c in range(15)))
    for r in range(15):
        line = f"{r:2d} " + " ".join(" X" if tiles[r][c] else " ." for c in range(15))
        print(line)

    result = draw_grid_overlay(image, bx, by, bw, bh, tiles)
    cv2.imwrite(args.output, result)
    print(f"\nSaved: {args.output}")


if __name__ == "__main__":
    main()
