#!/usr/bin/env python3
"""
Crossplay grid overlay tool.
Detects the board region, highlights tile cells, and builds a tile audit sheet.
"""

import json
import os
import shutil
import struct
import subprocess
import sys
import zlib
from pathlib import Path

import cv2
import numpy as np

from solver import TILE_PTS, load_board_json


SCORE_CROP_WIDTH_RATIO = 0.35
SCORE_CROP_HEIGHT_RATIO = 0.45
SCORE_ANALYSIS_THRESHOLDS = (150, 170, 190, 210)
SCORE_HOLE_MIN_AREA_RATIO = 0.001
SCORE_BORDER_RATIO = 0.03
SCORE_GLYPH_MIN_AREA_RATIO = 0.01
SCORE_GLYPH_MAX_AREA_RATIO = 0.40
SCORE_OCR_THRESHOLD = 180
SCORE_OCR_BORDER = 20
SCORE_OCR_PSM = 10
SCORE_OCR_TIMEOUT_SECONDS = 5
LETTER_CROP_LEFT_RATIO = 0.15
LETTER_CROP_RIGHT_RATIO = 0.80
LETTER_CROP_TOP_RATIO = 0.10
LETTER_CROP_BOTTOM_RATIO = 0.85
LETTER_OCR_THRESHOLDS = (180, 190)
LETTER_OCR_BORDER = 20
SCORE_POINT_HOLES = {
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
YELLOW_HIGHLIGHT_LOWER = np.array([10, 25, 60])
YELLOW_HIGHLIGHT_UPPER = np.array([55, 255, 255])
AUDIT_METADATA_KEY = "crossplay-audit"
AUDIT_PAGE_HEADER_HEIGHT = 64
AUDIT_CARD_WIDTH = 268
AUDIT_CARD_HEIGHT = 202
AUDIT_IMAGE_SIZE = 120
AUDIT_IMAGE_TOP = 72
AUDIT_WHOLE_LEFT = 8
AUDIT_SCORE_LEFT = 140


def remove_yellow_highlight(image):
    """Inpaint the yellow last-move outline in a tile image."""
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(
        hsv, YELLOW_HIGHLIGHT_LOWER, YELLOW_HIGHLIGHT_UPPER
    )
    if cv2.countNonZero(mask) == 0:
        return image
    return cv2.inpaint(image, mask, 2, cv2.INPAINT_TELEA)


def _find_tesseract():
    """Return a usable Tesseract executable, plus any setup error."""
    configured = os.environ.get("CROSSPLAY_TESSERACT")
    if (
            configured is not None
            and configured.strip().lower() in {
                "", "0", "false", "none", "off"
            }):
        return None, None
    candidate = configured or "tesseract"
    executable = shutil.which(candidate)
    if executable is None:
        if configured:
            return (
                None,
                "Configured Tesseract executable was not found; "
                "using topology fallback.",
            )
        return None, None

    try:
        result = subprocess.run(
            [executable, "--list-langs"],
            capture_output=True,
            timeout=SCORE_OCR_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return (
            None,
            "Tesseract language check timed out; using topology fallback.",
        )
    except OSError:
        return (
            None,
            "Tesseract language check failed; using topology fallback.",
        )

    output = result.stdout + b"\n" + result.stderr
    languages = {
        line.strip()
        for line in output.decode("utf-8", errors="replace").splitlines()
    }
    if result.returncode != 0:
        return (
            None,
            "Tesseract could not load its language data; "
            "using topology fallback.",
        )
    if "eng" not in languages:
        return (
            None,
            "Tesseract English language data is unavailable; "
            "using topology fallback.",
        )
    return executable, None


def _prepare_score_ocr_image(score_image):
    """Prepare a score corner as dark digits on a white OCR canvas."""
    if score_image is None or score_image.size == 0:
        return None
    if score_image.ndim == 3:
        gray = cv2.cvtColor(score_image, cv2.COLOR_BGR2GRAY)
    else:
        gray = score_image
    interpolation = (
        cv2.INTER_AREA
        if max(gray.shape[:2]) > AUDIT_IMAGE_SIZE
        else cv2.INTER_CUBIC
    )
    gray = cv2.resize(
        gray,
        (AUDIT_IMAGE_SIZE, AUDIT_IMAGE_SIZE),
        interpolation=interpolation,
    )
    _, bright_glyph = cv2.threshold(
        gray,
        SCORE_OCR_THRESHOLD,
        255,
        cv2.THRESH_BINARY,
    )
    dark_glyph = 255 - bright_glyph
    return cv2.copyMakeBorder(
        dark_glyph,
        SCORE_OCR_BORDER,
        SCORE_OCR_BORDER,
        SCORE_OCR_BORDER,
        SCORE_OCR_BORDER,
        cv2.BORDER_CONSTANT,
        value=255,
    )


def _prepare_letter_ocr_image(cell_image, threshold):
    """Crop and threshold the large tile letter for OCR."""
    if cell_image is None or cell_image.size == 0:
        return None
    if cell_image.ndim == 3:
        gray = cv2.cvtColor(cell_image, cv2.COLOR_BGR2GRAY)
    else:
        gray = cell_image
    height, width = gray.shape[:2]
    x1 = min(
        width - 1,
        int(round(width * LETTER_CROP_LEFT_RATIO)),
    )
    x2 = max(
        x1 + 1,
        min(width, int(round(width * LETTER_CROP_RIGHT_RATIO))),
    )
    y1 = min(
        height - 1,
        int(round(height * LETTER_CROP_TOP_RATIO)),
    )
    y2 = max(
        y1 + 1,
        min(height, int(round(height * LETTER_CROP_BOTTOM_RATIO))),
    )
    crop = gray[y1:y2, x1:x2]
    if crop.size == 0:
        return None
    crop = cv2.resize(
        crop,
        (AUDIT_IMAGE_SIZE, AUDIT_IMAGE_SIZE),
        interpolation=cv2.INTER_CUBIC,
    )
    _, bright_glyph = cv2.threshold(
        crop,
        threshold,
        255,
        cv2.THRESH_BINARY,
    )
    dark_glyph = 255 - bright_glyph
    return cv2.copyMakeBorder(
        dark_glyph,
        LETTER_OCR_BORDER,
        LETTER_OCR_BORDER,
        LETTER_OCR_BORDER,
        LETTER_OCR_BORDER,
        cv2.BORDER_CONSTANT,
        value=255,
    )


def _run_tesseract_symbol(prepared, executable, whitelist, label):
    """Run single-symbol OCR on a prepared image."""
    if prepared is None:
        return None, None
    fallback = (
        "topology fallback"
        if label == "Score"
        else "visual fallback"
    )
    try:
        encoded_ok, encoded = cv2.imencode(".png", prepared)
    except cv2.error:
        return None, f"{label} OCR image encoding failed; using {fallback}."
    if not encoded_ok:
        return None, f"{label} OCR image encoding failed; using {fallback}."

    try:
        result = subprocess.run(
            [
                executable,
                "stdin",
                "stdout",
                "--psm",
                str(SCORE_OCR_PSM),
                "-l",
                "eng",
                "-c",
                f"tessedit_char_whitelist={whitelist}",
            ],
            input=encoded.tobytes(),
            capture_output=True,
            timeout=SCORE_OCR_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return None, (
            f"Tesseract {label.lower()} OCR timed out; "
            f"using {fallback}."
        )
    except OSError:
        return None, (
            f"Tesseract {label.lower()} OCR failed; using {fallback}."
        )

    if result.returncode != 0:
        return None, (
            f"Tesseract {label.lower()} OCR failed; using {fallback}."
        )
    return result.stdout.decode("utf-8", errors="replace").strip(), None


def _read_score_digit(score_image, executable):
    """Read one score digit with Tesseract, returning an error separately."""
    text, error = _run_tesseract_symbol(
        _prepare_score_ocr_image(score_image),
        executable,
        "0123456789",
        "Score",
    )
    if error or text is None:
        return None, error
    if not text.isascii() or not text.isdigit():
        return None, None
    digit = int(text)
    if text != str(digit) or not 0 <= digit <= 10:
        return None, None
    return digit, None


def _read_tile_letter(cell_image, executable):
    """Read a stable tile letter across two nearby thresholds."""
    observations = []
    for threshold in LETTER_OCR_THRESHOLDS:
        text, error = _run_tesseract_symbol(
            _prepare_letter_ocr_image(cell_image, threshold),
            executable,
            "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
            "Letter",
        )
        if error:
            return None, error
        if (
                text is None
                or len(text) != 1
                or not text.isascii()
                or not "A" <= text <= "Z"):
            return None, None
        observations.append(text)
    if len(set(observations)) != 1:
        return None, None
    return observations[0], None


def analyze_tile_letter(letter, ocr_letter=None):
    """Compare stable letter OCR with a transcribed tile claim."""
    if (
            not isinstance(letter, str)
            or len(letter) != 1
            or not letter.isascii()
            or not letter.isalpha()):
        return {
            "letter_check": "unavailable",
            "letter_method": "none",
            "letter_ocr": None,
            "letter_reason": "Letter check requires a transcribed ASCII letter.",
        }
    if (
            ocr_letter is not None
            and (
                not isinstance(ocr_letter, str)
                or len(ocr_letter) != 1
                or not ocr_letter.isascii()
                or not "A" <= ocr_letter <= "Z")):
        raise ValueError("OCR tile letter must be one uppercase ASCII letter")
    claimed_letter = letter.upper()
    if ocr_letter is None:
        return {
            "letter_check": "unavailable",
            "letter_method": "none",
            "letter_ocr": None,
            "letter_reason": (
                "No stable letter OCR reading is available; "
                "compare the source tile visually."
            ),
        }
    if ocr_letter == claimed_letter:
        return {
            "letter_check": "clear",
            "letter_method": "tesseract",
            "letter_ocr": ocr_letter,
            "letter_reason": (
                f"Tesseract read {ocr_letter}, consistent with "
                f"JSON's {claimed_letter}."
            ),
        }
    return {
        "letter_check": "review",
        "letter_method": "tesseract",
        "letter_ocr": ocr_letter,
        "letter_reason": (
            f"Tesseract read {ocr_letter} rather than JSON's "
            f"{claimed_letter}; verify the source tile."
        ),
    }


def _score_hole_count(score_image, threshold):
    """Count significant enclosed loops in a thresholded score glyph."""
    if score_image is None or score_image.size == 0:
        return None
    if score_image.ndim == 3:
        gray = cv2.cvtColor(score_image, cv2.COLOR_BGR2GRAY)
    else:
        gray = score_image
    interpolation = (
        cv2.INTER_AREA
        if max(gray.shape[:2]) > AUDIT_IMAGE_SIZE
        else cv2.INTER_CUBIC
    )
    gray = cv2.resize(
        gray,
        (AUDIT_IMAGE_SIZE, AUDIT_IMAGE_SIZE),
        interpolation=interpolation,
    )
    mask = np.where(gray >= threshold, 255, 0).astype(np.uint8)
    border = max(
        2,
        int(round(min(mask.shape[:2]) * SCORE_BORDER_RATIO)),
    )
    mask[:border, :] = 0
    mask[-border:, :] = 0
    mask[:, :border] = 0
    mask[:, -border:] = 0
    foreground_ratio = cv2.countNonZero(mask) / mask.size
    if not (
            SCORE_GLYPH_MIN_AREA_RATIO
            <= foreground_ratio
            <= SCORE_GLYPH_MAX_AREA_RATIO):
        return None
    contours, hierarchy = cv2.findContours(
        mask,
        cv2.RETR_CCOMP,
        cv2.CHAIN_APPROX_SIMPLE,
    )
    if hierarchy is None:
        return 0
    min_area = mask.size * SCORE_HOLE_MIN_AREA_RATIO
    return sum(
        1
        for index, relation in enumerate(hierarchy[0])
        if relation[3] != -1
        and cv2.contourArea(contours[index]) >= min_area
    )


def analyze_score_corner(score_image, letter, is_blank, ocr_digit=None):
    """Compare OCR or stable score topology with a board JSON claim."""
    if (
            ocr_digit is not None
            and (type(ocr_digit) is not int or not 0 <= ocr_digit <= 10)):
        raise ValueError("OCR score digit must be an integer from 0 to 10")
    if (
            not isinstance(letter, str)
            or len(letter) != 1
            or not letter.isascii()
            or not letter.isalpha()):
        return {
            "score_check": "unavailable",
            "score_holes": None,
            "score_method": "none",
            "score_ocr_digit": None,
            "score_reason": "Score check requires a transcribed ASCII letter.",
        }
    natural_points = TILE_PTS.get(letter.upper())
    if natural_points not in SCORE_POINT_HOLES:
        return {
            "score_check": "unavailable",
            "score_holes": None,
            "score_method": "none",
            "score_ocr_digit": None,
            "score_reason": "Score check has no topology for this tile value.",
        }

    claimed_points = 0 if is_blank else natural_points
    alternative_points = natural_points if is_blank else 0
    if ocr_digit is not None:
        if ocr_digit == claimed_points:
            return {
                "score_check": "clear",
                "score_holes": None,
                "score_method": "tesseract",
                "score_ocr_digit": ocr_digit,
                "score_reason": (
                    f"Tesseract read {ocr_digit}, consistent with "
                    f"JSON's {claimed_points}."
                ),
            }
        if ocr_digit == alternative_points:
            return {
                "score_check": "review",
                "score_holes": None,
                "score_method": "tesseract",
                "score_ocr_digit": ocr_digit,
                "score_reason": (
                    f"Tesseract read {ocr_digit} rather than JSON's "
                    f"{claimed_points}; verify blank casing."
                ),
            }
        return {
            "score_check": "review",
            "score_holes": None,
            "score_method": "tesseract",
            "score_ocr_digit": ocr_digit,
            "score_reason": (
                f"Tesseract read {ocr_digit}, which does not match JSON's "
                f"{claimed_points}; verify the score and blank casing."
            ),
        }

    expected_holes = SCORE_POINT_HOLES[claimed_points]
    alternative_holes = SCORE_POINT_HOLES[alternative_points]
    observations = tuple(
        _score_hole_count(score_image, threshold)
        for threshold in SCORE_ANALYSIS_THRESHOLDS
    )
    stable = None not in observations and len(set(observations)) == 1
    if expected_holes == alternative_holes:
        return {
            "score_check": "ambiguous",
            "score_holes": observations[0] if stable else None,
            "score_method": "topology",
            "score_ocr_digit": None,
            "score_reason": (
                f"Score topology cannot distinguish {claimed_points} from "
                f"{alternative_points}; verify the corner visually."
            ),
        }
    if not stable:
        return {
            "score_check": "unavailable",
            "score_holes": None,
            "score_method": "topology",
            "score_ocr_digit": None,
            "score_reason": (
                "Score shape was not stable across thresholds; verify visually."
            ),
        }

    holes = observations[0]
    loop_word = "loop" if holes == 1 else "loops"

    if holes == expected_holes:
        return {
            "score_check": "clear",
            "score_holes": holes,
            "score_method": "topology",
            "score_ocr_digit": None,
            "score_reason": (
                f"Score corner has {holes} enclosed {loop_word}, consistent "
                f"with {claimed_points}."
            ),
        }
    if holes == alternative_holes:
        return {
            "score_check": "review",
            "score_holes": holes,
            "score_method": "topology",
            "score_ocr_digit": None,
            "score_reason": (
                f"Score corner has {holes} enclosed {loop_word}, matching "
                f"{alternative_points} rather than JSON's {claimed_points}; "
                "verify blank casing."
            ),
        }
    return {
        "score_check": "review",
        "score_holes": holes,
        "score_method": "topology",
        "score_ocr_digit": None,
        "score_reason": (
            f"Score corner has {holes} enclosed {loop_word}, which does not "
            f"match JSON's {claimed_points}; verify the score and blank casing."
        ),
    }


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
        x1, x2 = int(w * 0.02), int(w * 0.98)
        # Top is unreliable from edges here; locate the board's first row by
        # the first blue-tile band, ignoring the rack in the bottom fifth.
        hsv_full = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        blue = cv2.inRange(hsv_full, np.array([85, 55, 80]), np.array([130, 255, 255]))
        row_blue = blue[: int(h * 0.8), x1:x2].mean(axis=1) / 255.0
        band = np.where(row_blue > 0.04)[0]
        y1 = int(band[0]) if len(band) else int(h * 0.25)
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
        board_h = y2 - y1  # keep in sync with aspect-corrected y range

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

    # Initial estimates from Phase 1 (edge-based detection).
    init_cell_h = board_h / 15.0
    init_cell_w = board_w / 15.0
    # Width detection is reliable (board spans nearly full image width).
    # Height detection is unreliable -- UI text/dividers above the board can
    # create strong edges that inflate the detected height. Trust width.
    trusted_cell = init_cell_w

    # Board region expressed in crop y-space.
    board_top_c = y1 - sy1
    board_bot_c = y2 - sy1
    tol = trusted_cell * 1.5  # board may sit up to ~1 cell outside edge bbox

    def _filter_to_board(clusters):
        return [c for c in clusters if (board_top_c - tol) <= c[0] <= (board_bot_c + tol)]

    left_cl_f = _filter_to_board(left_cl)
    right_cl_f = _filter_to_board(right_cl)

    # Span-filter clusters before pattern matching. Premium squares on the
    # edge strip produce narrow clusters (~one cell tall). Tile racks and
    # merged tile-block clusters produce much wider spans. A span filter at
    # 1.8 cells removes the worst offenders while keeping premium clusters
    # even when they're adjacent to an edge tile.
    span_limit = trusted_cell * 1.8

    def _span_filter(clusters):
        return [c for c in clusters if (c[2] - c[1]) <= span_limit]

    left_cl_f = _span_filter(left_cl_f)
    right_cl_f = _span_filter(right_cl_f)

    # Col-0 premium pattern: 3L, 3W, 2L, 3W, 3L at rows 0, 3, 7, 11, 14.
    COL0_ROWS = [0, 3, 7, 11, 14]

    def _align_to_pattern(cluster_ys, cell):
        """Find the row_0_y that maximizes the number of clusters matching a
        premium row in COL0_ROWS, tolerating outlier clusters that don't
        correspond to any premium (e.g. merged tile clusters that survived
        the span filter). Returns (row_0_y, matched_rows) or (None, None).

        Returns (row_0_y, matched_rows, refined_cell) or (None, None, None).

        Algorithm: for every (cluster, hypothesized_row) pair, compute the
        implied row_0_y, then count how many other clusters land within 0.3
        cells of any premium row. Pick the alignment with the most matches
        (and lowest residual error as tiebreaker). After finding the best
        alignment, refine cell size by linear-regressing matched-cluster y
        positions against their assigned row numbers -- this is substantially
        more accurate than the input `cell` estimate because premium-to-
        premium distances span many cells and aren't subject to the edge-
        detection fuzz that inflates width-based estimates.
        """
        if len(cluster_ys) < 2:
            return None, None, None

        tol_cells = 0.3  # how close a cluster must be to a premium row to count
        best = None  # (match_count, row_0_y, total_error, matched_pairs)

        for anchor_idx, anchor_y in enumerate(cluster_ys):
            for anchor_row in COL0_ROWS:
                row_0_y = anchor_y - anchor_row * cell
                matches = 0
                err = 0.0
                pairs = []  # (cluster_y, matched_row)
                for cy in cluster_ys:
                    est = (cy - row_0_y) / cell
                    nearest = min(COL0_ROWS, key=lambda r: abs(est - r))
                    delta = abs(est - nearest)
                    if delta <= tol_cells:
                        matches += 1
                        err += delta
                        pairs.append((cy, nearest))
                if best is None or matches > best[0] or (
                        matches == best[0] and err < best[2]):
                    best = (matches, row_0_y, err, pairs)

        if best is None or best[0] < 3:
            return None, None, None

        # Refine cell size from matched clusters. Fit y = row*cell + row_0_y
        # using the endpoints (first and last matched pair) -- robust to
        # outliers and exact when pairs land cleanly on integer rows.
        pairs = sorted(best[3])  # sorted by y
        first_cy, first_row = pairs[0]
        last_cy, last_row = pairs[-1]
        if last_row > first_row:
            refined_cell = (last_cy - first_cy) / (last_row - first_row)
            row_0_y = first_cy - first_row * refined_cell
        else:
            refined_cell = cell
            row_0_y = best[1]

        matched_rows = sorted(set(r for _, r in pairs))
        return row_0_y, matched_rows, refined_cell

    # Try pattern matching on each side; prefer the side with more matches.
    best_side = "edge"
    row_0_y = None
    matched_rows = None
    refined_cell = None

    for side_name, clusters in [("left", left_cl_f), ("right", right_cl_f)]:
        ys = sorted(c[0] for c in clusters)
        r0, matched, rc = _align_to_pattern(ys, trusted_cell)
        if r0 is not None and (row_0_y is None or len(matched) > len(matched_rows or [])):
            row_0_y = r0
            matched_rows = matched
            refined_cell = rc
            best_side = side_name

    cell = refined_cell if refined_cell is not None else trusted_cell

    if row_0_y is not None:
        grid_top = row_0_y - cell * 0.5
        anchor_used = f"pattern ({best_side}, matched rows {matched_rows})"
    else:
        # Pattern match failed; try naive first/last cluster approach with
        # sanity check against trusted cell size.
        if len(left_cl_f) >= 2 and len(right_cl_f) >= 2:
            lys = sorted(c[0] for c in left_cl_f)
            rys = sorted(c[0] for c in right_cl_f)
            top_y = (lys[0] + rys[0]) // 2
            bot_y = (lys[-1] + rys[-1]) // 2
            cand = (bot_y - top_y) / 14.0
            if abs(cand - trusted_cell) / trusted_cell <= 0.10:
                cell = cand
                # Treat naive's top_y as row 0's center -- this is a hypothesis,
                # but tracking row_0_y lets us recompute grid_top cleanly if
                # horizontal anchor refines the cell size later.
                row_0_y = top_y
                grid_top = row_0_y - cell * 0.5
                anchor_used = "anchor (naive, sanity-passed)"
            else:
                grid_top = board_top_c
                anchor_used = f"edge (pattern+naive failed)"
        else:
            grid_top = board_top_c
            anchor_used = "edge (too few clusters)"

    grid_h = int(round(cell * 15))
    grid_w = int(round(cell * 15))

    # Horizontal anchor: scan the top row (center of row 0) for column
    # premiums. The crop region may not include row 0 on dense boards (if
    # Phase 1's aspect correction snapped y-range down into the tile cluster),
    # so scan the original image directly using absolute coordinates.
    abs_row0_center = int(sy1 + grid_top + cell * 0.5)
    band_y1 = max(0, abs_row0_center - int(cell * 0.4))
    band_y2 = min(h, abs_row0_center + int(cell * 0.4))
    if band_y2 <= band_y1:
        top_h_cl_f = []
    else:
        band_hsv = cv2.cvtColor(image[band_y1:band_y2, x1:x2], cv2.COLOR_BGR2HSV)
        top_row_sat = np.mean(band_hsv[:, :, 1], axis=0)
        top_h_cl = find_premium_clusters(top_row_sat)
        x_tol = trusted_cell * 0.6
        top_h_cl_f = [c for c in top_h_cl if -x_tol <= c[0] <= board_w + x_tol]

    if len(top_h_cl_f) >= 2:
        # We have accurate cell size from the vertical pattern match's linear
        # regression. Use horizontal anchor ONLY for x-position refinement --
        # specifically, use the first cluster as col 0's center. Deriving cell
        # from first/last cluster distance is noisier than the vertical
        # pattern's 11-cell baseline, so we don't override `cell` here.
        # Column 0 has a 3L premium, so the leftmost cluster is col 0's center.
        left_x = top_h_cl_f[0][0]
        grid_left = left_x - cell * 0.5
        abs_x1 = int(x1 + grid_left)
        x_anchor_used = "anchor (x-position only)"
    else:
        abs_x1 = x1
        x_anchor_used = "edge (too few top clusters)"

    abs_y1 = int(sy1 + grid_top)

    # Final clamp: board must fit within image bounds.
    if abs_x1 + grid_w > w:
        grid_w = w - abs_x1
    if abs_y1 + grid_h > h:
        grid_h = h - abs_y1
    if abs_x1 < 0:
        grid_w += abs_x1
        abs_x1 = 0
    if abs_y1 < 0:
        grid_h += abs_y1
        abs_y1 = 0

    # Invariant: Crossplay boards are always 15x15 squares of identical cells.
    # If grid_w and grid_h diverge, something went wrong upstream -- either a
    # detection bug or the image-bounds clamp cropped one axis. Enforce square
    # by collapsing to a single side length, and warn so it's visible in logs.
    if grid_w != grid_h:
        side = min(grid_w, grid_h)
        print(f"  WARNING: Non-square grid detected ({grid_w}x{grid_h}); "
              f"collapsing to {side}x{side}")
        grid_w = grid_h = side

    # Sanity check: derived cell size should match what we'd get from the
    # final square grid. If not, there's a logic bug.
    final_cell = grid_w / 15.0
    if abs(final_cell - cell) > 0.5:
        print(f"  WARNING: Cell size mismatch: tracked cell={cell:.1f}px, "
              f"final cell={final_cell:.1f}px")

    print(f"  Phase1 edge cell: {init_cell_w:.1f}px (w) / {init_cell_h:.1f}px (h)")
    print(f"  L/R clusters: {len(left_cl)}/{len(right_cl)} "
          f"(filtered: {len(left_cl_f)}/{len(right_cl_f)})")
    print(f"  Vertical: {anchor_used}, cell={cell:.1f}px")
    print(f"  Horizontal: {x_anchor_used}")

    assert grid_w == grid_h, f"grid must be square: got {grid_w}x{grid_h}"
    return abs_x1, abs_y1, grid_w, grid_h


def detect_tile_cells(board_crop, grid_size=15):
    """Return a 15x15 bool array: True where a blue tile is detected."""
    hsv = cv2.cvtColor(board_crop, cv2.COLOR_BGR2HSV)
    # Tuned for Crossplay blue tiles (H~85-130, S~55+, V~80+)
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


def collect_tile_audit_entries(detected_tiles, board, blanks, grid_size=15):
    """Return audit entries for every detected or transcribed tile."""
    detected = {
        (r, c)
        for r in range(grid_size)
        for c in range(grid_size)
        if detected_tiles[r][c]
    }
    transcribed = {
        (r, c)
        for r in range(grid_size)
        for c in range(grid_size)
        if board[r][c] != "."
    }

    entries = []
    for r, c in sorted(detected | transcribed):
        in_board = (r, c) in transcribed
        is_blank = in_board and (r, c) in blanks
        letter = board[r][c] if in_board else None
        entries.append({
            "row": r,
            "col": c,
            "detected": (r, c) in detected,
            "transcribed": in_board,
            "letter": letter,
            "blank": is_blank,
            "points": (
                0
                if is_blank
                else TILE_PTS.get(letter, 0) if in_board else None
            ),
        })
    return entries


def draw_tile_audit(
        image, bx, by, bw, bh, detected_tiles, board, blanks,
        grid_size=15, columns=4):
    """Create cards comparing source letters and scores with board JSON."""
    entries = collect_tile_audit_entries(
        detected_tiles, board, blanks, grid_size
    )

    page_header_h = AUDIT_PAGE_HEADER_HEIGHT
    card_w = AUDIT_CARD_WIDTH
    card_h = AUDIT_CARD_HEIGHT
    rows = max(1, (len(entries) + columns - 1) // columns)
    sheet = np.full(
        (page_header_h + rows * card_h, columns * card_w, 3),
        255,
        dtype=np.uint8,
    )

    font = cv2.FONT_HERSHEY_SIMPLEX
    cv2.putText(
        sheet,
        "Tile audit: compare each source tile and score with board JSON",
        (10, 24),
        font,
        0.62,
        (20, 20, 20),
        2,
        cv2.LINE_AA,
    )
    cv2.putText(
        sheet,
        "Red LETTER!/SCORE! = conflict; VERIFY/CHECK = unresolved",
        (10, 50),
        font,
        0.52,
        (20, 20, 20),
        1,
        cv2.LINE_AA,
    )

    if not entries:
        cv2.putText(
            sheet,
            "No detected or transcribed tiles.",
            (10, page_header_h + 40),
            font,
            0.6,
            (0, 0, 180),
            2,
            cv2.LINE_AA,
        )
        return sheet, entries

    cell_w = bw / grid_size
    cell_h = bh / grid_size
    image_h, image_w = image.shape[:2]
    image_size = AUDIT_IMAGE_SIZE
    prepared_images = {}
    tesseract, tesseract_error = _find_tesseract()
    if tesseract_error:
        print(f"WARNING: {tesseract_error}", file=sys.stderr)
    tesseract_warning_shown = tesseract_error is not None

    for entry in entries:
        r, c = entry["row"], entry["col"]
        x1 = max(0, int(round(bx + c * cell_w)))
        x2 = min(image_w, int(round(bx + (c + 1) * cell_w)))
        y1 = max(0, int(round(by + r * cell_h)))
        y2 = min(image_h, int(round(by + (r + 1) * cell_h)))
        cell = image[y1:y2, x1:x2]
        if cell.size == 0:
            entry.update({
                "letter_check": "unavailable",
                "letter_method": "none",
                "letter_ocr": None,
                "letter_reason": "Source tile crop failed.",
                "score_check": "unavailable",
                "score_holes": None,
                "score_method": "none",
                "score_ocr_digit": None,
                "score_reason": "Score corner crop failed.",
            })
            continue

        clean_cell = remove_yellow_highlight(cell)
        whole = cv2.resize(
            clean_cell,
            (image_size, image_size),
            interpolation=cv2.INTER_CUBIC,
        )
        score_y2 = max(
            1, int(cell.shape[0] * SCORE_CROP_HEIGHT_RATIO)
        )
        score_x1 = min(
            cell.shape[1] - 1,
            int(cell.shape[1] * (1.0 - SCORE_CROP_WIDTH_RATIO)),
        )
        score_crop = clean_cell[:score_y2, score_x1:]
        score = cv2.resize(
            score_crop,
            (image_size, image_size),
            interpolation=cv2.INTER_CUBIC,
        )
        ocr_digit = None
        ocr_letter = None
        if entry["transcribed"] and tesseract is not None:
            ocr_digit, ocr_error = _read_score_digit(score, tesseract)
            if ocr_error:
                if not tesseract_warning_shown:
                    print(f"WARNING: {ocr_error}", file=sys.stderr)
                    tesseract_warning_shown = True
                tesseract = None
        if entry["transcribed"] and tesseract is not None:
            ocr_letter, ocr_error = _read_tile_letter(
                clean_cell,
                tesseract,
            )
            if ocr_error:
                if not tesseract_warning_shown:
                    print(f"WARNING: {ocr_error}", file=sys.stderr)
                    tesseract_warning_shown = True
                tesseract = None
        entry.update(
            analyze_score_corner(
                score,
                entry["letter"],
                entry["blank"],
                ocr_digit=ocr_digit,
            )
            if entry["transcribed"]
            else {
                "score_check": "unavailable",
                "score_holes": None,
                "score_method": "none",
                "score_ocr_digit": None,
                "score_reason": (
                    "Score check requires a transcribed board tile."
                ),
            }
        )
        entry.update(
            analyze_tile_letter(entry["letter"], ocr_letter=ocr_letter)
            if entry["transcribed"]
            else {
                "letter_check": "unavailable",
                "letter_method": "none",
                "letter_ocr": None,
                "letter_reason": (
                    "Letter check requires a transcribed board tile."
                ),
            }
        )
        prepared_images[(r, c)] = (whole, score)

    for index, entry in enumerate(entries):
        card_row, card_col = divmod(index, columns)
        x = card_col * card_w
        y = page_header_h + card_row * card_h
        r, c = entry["row"], entry["col"]

        detection_mismatch = entry["detected"] != entry["transcribed"]
        letter_review = entry.get("letter_check") == "review"
        score_check = entry.get("score_check")
        score_review = score_check == "review"
        score_attention = (
            entry["transcribed"]
            and score_check in {"review", "ambiguous", "unavailable"}
        )
        mismatch = detection_mismatch or letter_review or score_review
        if mismatch:
            header_color = (210, 210, 255)
            border_color = (0, 0, 200)
        elif entry["blank"] or score_attention:
            header_color = (180, 245, 255)
            border_color = (0, 150, 190)
        else:
            header_color = (238, 238, 238)
            border_color = (150, 150, 150)

        cv2.rectangle(
            sheet, (x + 2, y + 2), (x + card_w - 3, y + card_h - 3),
            border_color, 2
        )
        cv2.rectangle(
            sheet, (x + 4, y + 4), (x + card_w - 5, y + 48),
            header_color, -1
        )

        detected_text = "yes" if entry["detected"] else "NO"
        cv2.putText(
            sheet,
            f"({entry['row']},{entry['col']}) detected: {detected_text}",
            (x + 9, y + 21),
            font,
            0.45,
            (20, 20, 20),
            1,
            cv2.LINE_AA,
        )

        if not entry["transcribed"]:
            json_text = "JSON: MISSING"
        elif entry["blank"]:
            json_text = (
                f"JSON: {entry['letter'].lower()} -> BLANK, 0 pts"
            )
        else:
            json_text = (
                f"JSON: {entry['letter']} -> {entry['points']} pts"
            )
        cv2.putText(
            sheet,
            json_text,
            (x + 9, y + 42),
            font,
            0.43,
            (20, 20, 20),
            1,
            cv2.LINE_AA,
        )
        if letter_review and score_review:
            cv2.putText(
                sheet,
                "BOTH!",
                (x + card_w - 57, y + 21),
                font,
                0.38,
                (0, 0, 200),
                1,
                cv2.LINE_AA,
            )
        elif letter_review:
            cv2.putText(
                sheet,
                "LETTER!",
                (x + card_w - 57, y + 21),
                font,
                0.31,
                (0, 0, 200),
                1,
                cv2.LINE_AA,
            )
        elif score_review:
            cv2.putText(
                sheet,
                "SCORE!",
                (x + card_w - 57, y + 21),
                font,
                0.38,
                (0, 0, 200),
                1,
                cv2.LINE_AA,
            )
        elif score_check == "ambiguous":
            cv2.putText(
                sheet,
                "VERIFY",
                (x + card_w - 57, y + 21),
                font,
                0.35,
                (0, 110, 155),
                1,
                cv2.LINE_AA,
            )
        elif score_check == "unavailable" and entry["transcribed"]:
            cv2.putText(
                sheet,
                "CHECK?",
                (x + card_w - 57, y + 21),
                font,
                0.35,
                (80, 80, 80),
                1,
                cv2.LINE_AA,
            )

        cv2.putText(
            sheet, "full tile", (x + 9, y + 65),
            font, 0.38, (70, 70, 70), 1, cv2.LINE_AA
        )
        cv2.putText(
            sheet, "score corner", (x + 140, y + 65),
            font, 0.38, (70, 70, 70), 1, cv2.LINE_AA
        )

        images = prepared_images.get((r, c))
        if images is None:
            cv2.putText(
                sheet, "CROP FAILED", (x + 9, y + 130),
                font, 0.52, (0, 0, 200), 2, cv2.LINE_AA
            )
            continue
        whole, score = images

        image_y = y + AUDIT_IMAGE_TOP
        sheet[
            image_y:image_y + image_size,
            x + AUDIT_WHOLE_LEFT:x + AUDIT_WHOLE_LEFT + image_size,
        ] = whole
        sheet[
            image_y:image_y + image_size,
            x + AUDIT_SCORE_LEFT:x + AUDIT_SCORE_LEFT + image_size,
        ] = score

    return sheet, entries


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


def _encode_image(extension, image):
    try:
        encoded_ok, encoded = cv2.imencode(extension, image)
    except cv2.error as exc:
        raise OSError(f"Could not encode image as {extension}") from exc
    if not encoded_ok:
        raise OSError(f"Could not encode image as {extension}")
    return encoded.tobytes()


def write_image(path, image):
    """Write an image, creating parent directories and surfacing failures."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    extension = output_path.suffix.lower() or ".png"
    output_path.write_bytes(_encode_image(extension, image))


def _png_chunk(chunk_type, data):
    checksum = zlib.crc32(chunk_type + data) & 0xffffffff
    return (
        struct.pack(">I", len(data))
        + chunk_type
        + data
        + struct.pack(">I", checksum)
    )


def _add_png_text(png_bytes, keyword, value):
    signature = b"\x89PNG\r\n\x1a\n"
    if not png_bytes.startswith(signature) or png_bytes[12:16] != b"IHDR":
        raise OSError("Could not add tile-audit metadata to invalid PNG")
    keyword_bytes = keyword.encode("ascii")
    if not keyword_bytes or len(keyword_bytes) > 79 or b"\0" in keyword_bytes:
        raise ValueError("PNG metadata keyword must contain 1-79 ASCII bytes")
    text_data = keyword_bytes + b"\0" + value.encode("latin-1")
    ihdr_length = struct.unpack(">I", png_bytes[8:12])[0]
    insert_at = 8 + 12 + ihdr_length
    return (
        png_bytes[:insert_at]
        + _png_chunk(b"tEXt", text_data)
        + png_bytes[insert_at:]
    )


def write_tile_audit(path, image, entries, columns=None):
    """Write an audit PNG with layout metadata for responsive HTML cards."""
    output_path = Path(path)
    if output_path.suffix.lower() not in ("", ".png"):
        raise OSError("Tile audit output must use a .png extension")
    if image.shape[1] % AUDIT_CARD_WIDTH != 0:
        raise ValueError("Tile audit sheet width does not match card layout")
    derived_columns = image.shape[1] // AUDIT_CARD_WIDTH
    if columns is None:
        columns = derived_columns
    elif type(columns) is not int or columns <= 0:
        raise ValueError("Tile audit column count must be a positive integer")
    elif columns != derived_columns:
        raise ValueError("Tile audit column count does not match sheet width")
    rows = max(1, (len(entries) + columns - 1) // columns)
    expected_height = AUDIT_PAGE_HEADER_HEIGHT + rows * AUDIT_CARD_HEIGHT
    if image.shape[0] != expected_height:
        raise ValueError("Tile audit sheet height does not match its entries")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    manifest = {
        "version": 1,
        "detection_known": True,
        "sheet": {
            "width": int(image.shape[1]),
            "height": int(image.shape[0]),
        },
        "layout": {
            "columns": int(columns),
            "page_header_height": AUDIT_PAGE_HEADER_HEIGHT,
            "card_width": AUDIT_CARD_WIDTH,
            "card_height": AUDIT_CARD_HEIGHT,
            "image_size": AUDIT_IMAGE_SIZE,
            "image_top": AUDIT_IMAGE_TOP,
            "whole_left": AUDIT_WHOLE_LEFT,
            "score_left": AUDIT_SCORE_LEFT,
        },
        "entries": entries,
    }
    manifest_json = json.dumps(
        manifest,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    png_bytes = _encode_image(".png", image)
    output_path.write_bytes(
        _add_png_text(png_bytes, AUDIT_METADATA_KEY, manifest_json)
    )


def read_image(path):
    """Read an image through Python I/O so Unicode Windows paths work."""
    image_path = Path(path)
    encoded = np.frombuffer(image_path.read_bytes(), dtype=np.uint8)
    return cv2.imdecode(encoded, cv2.IMREAD_COLOR)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Crossplay grid overlay")
    parser.add_argument("image", help="Path to screenshot")
    parser.add_argument("-o", "--output", default="grid_overlay.png")
    parser.add_argument(
        "--board-json",
        help="Board JSON to compare against source tiles",
    )
    parser.add_argument(
        "--tile-audit",
        help="Output path for board-aware tile audit PNG",
    )
    args = parser.parse_args()

    if bool(args.board_json) != bool(args.tile_audit):
        parser.error("--board-json and --tile-audit must be used together")

    try:
        image = read_image(args.image)
    except OSError as exc:
        parser.error(f"could not read image: {exc}")
    if image is None:
        parser.error(f"could not decode image: {args.image}")

    print(f"Image: {image.shape[1]}x{image.shape[0]}")

    bx, by, bw, bh = find_board_region(image)
    print(f"Board: x={bx} y={by} w={bw} h={bh}, cell={bw/15:.1f}px")

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
    try:
        write_image(args.output, result)
    except OSError as exc:
        parser.error(str(exc))
    print(f"\nSaved: {args.output}")

    if args.tile_audit:
        try:
            board, blanks = load_board_json(args.board_json)
        except (OSError, ValueError) as exc:
            parser.error(f"could not load board: {exc}")
        audit, entries = draw_tile_audit(
            image, bx, by, bw, bh, tiles, board, blanks
        )
        try:
            write_tile_audit(args.tile_audit, audit, entries)
        except OSError as exc:
            parser.error(str(exc))
        detection_mismatches = sum(
            entry["detected"] != entry["transcribed"]
            for entry in entries
        )
        score_reviews = sum(
            entry.get("score_check") == "review"
            for entry in entries
        )
        letter_reviews = sum(
            entry.get("letter_check") == "review"
            for entry in entries
        )
        score_ocr_reads = sum(
            entry.get("score_method") == "tesseract"
            for entry in entries
        )
        letter_ocr_reads = sum(
            entry.get("letter_method") == "tesseract"
            for entry in entries
        )
        topology_fallbacks = sum(
            entry.get("score_method") == "topology"
            for entry in entries
        )
        print(
            f"Tile audit: {len(entries)} cards, "
            f"{detection_mismatches} detection/JSON mismatches, "
            f"{letter_reviews} letter/JSON reviews, "
            f"{score_reviews} score/JSON reviews, "
            f"{letter_ocr_reads} letter OCR readings, "
            f"{score_ocr_reads} score OCR readings, "
            f"{topology_fallbacks} topology fallbacks"
        )
        print(f"Saved: {args.tile_audit}")


if __name__ == "__main__":
    main()
