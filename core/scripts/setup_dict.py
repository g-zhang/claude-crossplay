#!/usr/bin/env python3
"""
Build the solver dictionary from NWL23.

Usage:
    python setup_dict.py --output dict.txt          # 145K playability list
    python setup_dict.py --output dict.txt --full    # full 196K list
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

WORDS_REPO = "https://github.com/scrabblewords/scrabblewords.git"
WORDS_DIR = Path(os.environ.get(
    "CROSSPLAY_WORDS_DIR",
    Path.home() / ".cache" / "claude-crossplay" / "scrabblewords",
))
NWL_PATH = Path("words") / "North-American"
UPLOAD_DIR = Path(os.environ.get(
    "CROSSPLAY_UPLOAD_DIR",
    "/mnt/user-data/uploads",
))

NWL_PLAYABILITY = "NWL2023-Playability.txt"
NWL_FULL = "NWL2023.txt"


def clone_if_needed(url, dest, label):
    dest = Path(dest)
    if (dest / ".git").exists():
        print(f"  {label}: already cloned at {dest}")
        return True
    if dest.exists():
        print(f"  {label}: FAILED - destination exists but is not a git checkout")
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"  {label}: cloning {url} ...")
    r = subprocess.run(
        ["git", "clone", "--depth", "1", url, str(dest)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if r.returncode == 0:
        print(f"  {label}: done")
        return True
    print(f"  {label}: FAILED - {r.stderr.strip()}")
    return False


def find_file(filename):
    candidates = [
        Path(WORDS_DIR) / NWL_PATH / filename,
        Path(UPLOAD_DIR) / filename,
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def load_playability(path, max_len=15):
    words = []
    with Path(path).open("r", encoding="utf-8") as f:
        for line in f:
            parts = line.split(None, 1)
            if len(parts) == 2:
                w = parts[1].strip().upper()
                if w.isalpha() and 2 <= len(w) <= max_len:
                    try:
                        words.append((w, int(parts[0])))
                    except ValueError:
                        pass
    return words


def load_full(path, max_len=15):
    words = []
    with Path(path).open("r", encoding="utf-8") as f:
        for line in f:
            w = line.split()[0].upper()
            if w.isalpha() and 2 <= len(w) <= max_len:
                words.append(w)
    return words


def main():
    p = argparse.ArgumentParser(description="NWL23 dictionary setup")
    p.add_argument("--output", default="dict.txt")
    p.add_argument("--full", action="store_true", help="Use full 196K list")
    p.add_argument("--max-length", type=int, default=15)
    args = p.parse_args()

    print("Fetching data...")
    if not clone_if_needed(WORDS_REPO, WORDS_DIR, "NWL23 words"):
        sys.exit(1)

    words = set()
    source = None

    if not args.full:
        path = find_file(NWL_PLAYABILITY)
        if path:
            print(f"\nLoading: {path}")
            ranked = load_playability(path, args.max_length)
            words = set(w for w, _ in ranked)
            source = f"NWL23-Playability ({len(words)} words)"

    if args.full or not words:
        path = find_file(NWL_FULL)
        if path:
            print(f"\nLoading: {path}")
            words = set(load_full(path, args.max_length))
            source = f"NWL23-Full ({len(words)} words)"

    if not words:
        print("\nERROR: No word lists found. Check network access to github.com")
        sys.exit(1)

    sorted_words = sorted(words)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        for w in sorted_words:
            f.write(w + "\n")

    by_len = {}
    for w in sorted_words:
        by_len.setdefault(len(w), 0)
        by_len[len(w)] += 1

    print(f"\nOK Dictionary: {args.output}")
    print(f"  Source: {source}")
    print(f"  Words: {len(sorted_words)}")
    print(f"  By length: {', '.join(f'{k}:{v}' for k,v in sorted(by_len.items())[:6])}...")


if __name__ == "__main__":
    main()
