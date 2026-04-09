#!/usr/bin/env python3
"""
Crossplay grid overlay tool.
Detects the board region, draws numbered grid lines, and highlights tile cells.
Output image lets Claude (or a human) read letters with exact row/col positions.
"""

import cv2
import numpy as np
import sys
from pathlib import Path


def find_premium_clusters(profile, min_sat=20, min_gap=5):
    """Find clusters of high-saturation pixels. Returns [(center, start, end), ...]."""
    above = np.where(profile > min_sat)[0]
    if len(above) == 0:
        return []
    clusters, start, prev = [], above[0], above[0]
    for idx in above[1:]:
        if idx - prev > min_gap:
            clusters.append((int((start + prev) / 2), int(start), int(prev)))
            start = idx
        prev = idx
    clusters.append((int((start + prev) / 2), int(start), int(prev)))
    return clusters


def find_board_region(image):
    """Find the board grid using premium squares at top AND bottom edges as anchors."""
    h, w = image.shape[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150)

    col_sums = np.sum(edges, axis=0)
    row_sums = np.sum(edges, axis=1)
    col_threshold = np.max(col_sums) * 0.15
    row_threshold = np.max(row_sums) * 0.15
    col_indices = np.where(col_sums > col_threshold)[0]
    row_indices = np.where(row_sums > row_threshold)[0]

    if len(col_indices) < 10 or len(row_indices) < 10:
        x1, x2, y1 = int(w * 0.02), int(w * 0.98), int(h * 0.25)
        y2 = y1 + (x2 - x1)
        return x1, y1, x2 - x1, y2 - y1

    x1, x2 = int(col_indices[0]), int(col_indices[-1])
    y1, y2 = int(row_indices[0]), int(row_indices[-1])
    board_w = x2 - x1
    board_h = y2 - y1

    if board_h > board_w * 1.5:
        target_size = board_w
        best_y, best_density = y1, 0
        for test_y in range(y1, y2 - target_size, 10):
            density = np.sum(edges[test_y:test_y + target_size, x1:x2])
            if density > best_density:
                best_density, best_y = density, test_y
        y1, y2 = best_y, best_y + target_size

    # --- Phase 2: anchor on premium squares at edges ---
    margin = int(board_w * 0.15)
    sy1 = max(0, y1 - margin)
    sy2 = min(h, y2 + margin)
    crop = image[sy1:sy2, x1:x2]
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    ch, cw = crop.shape[:2]

    strip = max(1, int(cw * 0.055))  # ~1 cell width on edge

    # Left and right edge saturation profiles (vertical)
    left_sat = np.mean(hsv[:, :strip, 1], axis=1)
    right_sat = np.mean(hsv[:, -strip:, 1], axis=1)
    left_cl = find_premium_clusters(left_sat)
    right_cl = find_premium_clusters(right_sat)

    if len(left_cl) >= 2 and len(right_cl) >= 2:
        # First/last clusters on left = centers of cells in rows 0 and 14
        top_y = (left_cl[0][0] + right_cl[0][0]) // 2
        bot_y = (left_cl[-1][0] + right_cl[-1][0]) // 2

        # Distance = 14 cell widths (center of row 0 to center of row 14)
        cell = (bot_y - top_y) / 14.0
        grid_top = top_y - cell * 0.5
        grid_bot = bot_y + cell * 0.5
        grid_h = int(round(grid_bot - grid_top))
        grid_w = int(round(cell * 15))

        # Find horizontal anchor: scan across the row 0 band for column premiums
        band_y1 = int(max(0, top_y - cell * 0.4))
        band_y2 = int(min(ch, top_y + cell * 0.4))
        top_row_sat = np.mean(hsv[band_y1:band_y2, :, 1], axis=0)
        top_h_cl = find_premium_clusters(top_row_sat)

        if len(top_h_cl) >= 2:
            left_x = top_h_cl[0][0]   # center of col 0 premium
            right_x = top_h_cl[-1][0]  # center of col 14 premium
            cell_x = (right_x - left_x) / 14.0
            grid_left = left_x - cell_x * 0.5
            grid_w = int(round(cell_x * 15))
            abs_x1 = int(x1 + grid_left)
        else:
            abs_x1 = x1

        abs_y1 = int(sy1 + grid_top)

        print(f"  Anchors: top_y={top_y} bot_y={bot_y} cell={cell:.1f}px")
        print(f"  L/R clusters: {len(left_cl)}/{len(right_cl)}")
        if len(top_h_cl) >= 2:
            print(f"  Top row clusters: {len(top_h_cl)}, cell_x={cell_x:.1f}px")

        return abs_x1, abs_y1, grid_w, grid_h

    # Fallback: original left-edge-only approach
    left_sat2 = np.mean(hsv[:, :int(cw * 0.07), 1], axis=1)
    colored = np.where(left_sat2 > 20)[0]
    if len(colored) > 10:
        gt = int(colored[0])
        gb = int(colored[-1])
        cell_est = (gb - gt) / 15
        pad = int(cell_est * 0.1)
        gt = max(0, gt - pad)
        gb = min(ch, gb + pad)
        gh = gb - gt
        side = max(gh, cw)
        ay1 = sy1 + gt
        ay2 = min(h, ay1 + side)
        side = ay2 - ay1
        return x1, ay1, min(w, x1 + side) - x1, side

    return x1, y1, x2 - x1, y2 - y1


def detect_tile_cells(board_crop, grid_size=15):
    """Return a 15x15 bool array: True where a blue tile is detected."""
    hsv = cv2.cvtColor(board_crop, cv2.COLOR_BGR2HSV)
    # Tuned for Crossplay blue tiles (H≈85-130, S≈55+, V≈80+)
    # Premium squares have S<63 and ratio<0.40, so 0.42 threshold separates cleanly
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
    # Add left padding if board is too close to image edge for row labels
    pad_left = 0
    if bx < 40:
        pad_left = 40 - bx
        out = cv2.copyMakeBorder(image, 0, 0, pad_left, 0, cv2.BORDER_CONSTANT, value=(255, 255, 255))
        bx += pad_left
    else:
        out = image.copy()
    cell_w = bw / grid_size
    cell_h = bh / grid_size

    # Green border on detected tile cells
    for r in range(grid_size):
        for c in range(grid_size):
            if tiles[r][c]:
                x1 = int(bx + c * cell_w) + 2
                y1 = int(by + r * cell_h) + 2
                x2 = int(bx + (c + 1) * cell_w) - 2
                y2 = int(by + (r + 1) * cell_h) - 2
                cv2.rectangle(out, (x1, y1), (x2, y2), (0, 220, 0), 2)

    # Grid lines (red, thin)
    for i in range(grid_size + 1):
        x = int(bx + i * cell_w)
        cv2.line(out, (x, int(by)), (x, int(by + bh)), (0, 0, 200), 1)
        y = int(by + i * cell_h)
        cv2.line(out, (int(bx), y), (int(bx + bw), y), (0, 0, 200), 1)

    # Column numbers (red, above board)
    font = cv2.FONT_HERSHEY_SIMPLEX
    fs = 0.55
    ft = 2
    # White background strip for labels
    cv2.rectangle(out, (int(bx) - 2, int(by) - 28), (int(bx + bw) + 2, int(by) - 1), (255, 255, 255), -1)
    for c in range(grid_size):
        cx = int(bx + (c + 0.35) * cell_w)
        cv2.putText(out, str(c), (cx, int(by) - 8), font, fs, (200, 0, 0), ft)

    # Row numbers (red, left of board)
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
    args = parser.parse_args()

    image = cv2.imread(str(args.image))
    if image is None:
        print(f"Error: Could not read {args.image}", file=sys.stderr)
        sys.exit(1)

    print(f"Image: {image.shape[1]}x{image.shape[0]}")

    bx, by, bw, bh = find_board_region(image)
    print(f"Board: x={bx} y={by} w={bw} h={bh}, cell={bw/15:.0f}x{bh/15:.0f}px")

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
