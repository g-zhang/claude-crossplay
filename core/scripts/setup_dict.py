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
import tempfile
from pathlib import Path

WORDS_REPO = "https://github.com/scrabblewords/scrabblewords.git"
WORDS_REV = "1170d075c02cb534aa0874c8edb246fc7343da58"
WORDS_DIR_VALUE = os.environ.get("CROSSPLAY_WORDS_DIR")
WORDS_DIR = (
    Path(WORDS_DIR_VALUE)
    if WORDS_DIR_VALUE
    else Path.home() / ".cache" / "claude-crossplay" / "scrabblewords"
)
NWL_PATH = Path("words") / "North-American"

NWL_PLAYABILITY = "NWL2023-Playability.txt"
NWL_FULL = "NWL2023.txt"


def run_git(args):
    """Run git with captured UTF-8 output."""
    return subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def normalize_repository_url(url):
    """Normalize common GitHub HTTPS and SSH remote spellings."""
    normalized = url.strip().rstrip("/")
    if normalized.endswith(".git"):
        normalized = normalized[:-4]
    if normalized.startswith("git@github.com:"):
        normalized = "https://github.com/" + normalized[len("git@github.com:"):]
    elif normalized.startswith("ssh://git@github.com/"):
        normalized = "https://github.com/" + normalized[len("ssh://git@github.com/"):]
    return normalized.lower()


def word_source_candidates(dest, filename):
    """Return repository-layout and flat-file candidates for an NWL23 file."""
    base = Path(dest)
    return (
        base / NWL_PATH / filename,
        base / filename,
    )


def has_word_sources(dest):
    """Return whether a directory contains a supported NWL23 source file."""
    return any(
        path.is_file()
        for filename in (NWL_PLAYABILITY, NWL_FULL)
        for path in word_source_candidates(dest, filename)
    )


def checkout_is_clean(dest):
    """Return whether tracked files in a source checkout are unchanged."""
    status = run_git([
        "-C", str(dest), "status", "--porcelain", "--untracked-files=no",
    ])
    return status.returncode == 0 and not status.stdout.strip()


def prepare_words_source(url, dest, label):
    """Prepare the pinned source revision or accept supplied plain files."""
    dest = Path(dest)
    git_dir = dest / ".git"

    if dest.exists() and not git_dir.exists():
        if not dest.is_dir():
            print(f"  {label}: FAILED - destination is not a directory")
            return False
        if has_word_sources(dest):
            print(f"  {label}: using supplied files at {dest}")
            return True
        if any(dest.iterdir()):
            print(f"  {label}: FAILED - destination has no supported NWL23 files")
            return False

    if git_dir.exists():
        current = run_git(["-C", str(dest), "rev-parse", "HEAD"])
        if current.returncode == 0 and current.stdout.strip() == WORDS_REV:
            if not checkout_is_clean(dest):
                print(f"  {label}: FAILED - pinned checkout has local changes")
                return False
            print(f"  {label}: pinned source ready at {dest}")
            return True
        remote = run_git(["-C", str(dest), "remote", "get-url", "origin"])
        if remote.returncode != 0:
            remote = run_git(["-C", str(dest), "remote", "add", "origin", url])
            if remote.returncode != 0:
                print(f"  {label}: FAILED - {remote.stderr.strip()}")
                return False
        elif (
                normalize_repository_url(remote.stdout)
                != normalize_repository_url(url)):
            print(f"  {label}: FAILED - existing checkout has an unexpected origin")
            return False
    else:
        dest.parent.mkdir(parents=True, exist_ok=True)
        init = run_git(["init", "--quiet", str(dest)])
        if init.returncode != 0:
            print(f"  {label}: FAILED - {init.stderr.strip()}")
            return False
        remote = run_git(["-C", str(dest), "remote", "add", "origin", url])
        if remote.returncode != 0:
            print(f"  {label}: FAILED - {remote.stderr.strip()}")
            return False

    print(f"  {label}: fetching pinned revision {WORDS_REV[:12]} ...")
    fetch = run_git([
        "-C", str(dest), "fetch", "--quiet", "--depth", "1", "origin", WORDS_REV,
    ])
    if fetch.returncode != 0:
        print(f"  {label}: FAILED - {fetch.stderr.strip()}")
        return False
    checkout = run_git([
        "-C", str(dest), "checkout", "--quiet", "--detach", "FETCH_HEAD",
    ])
    if checkout.returncode != 0:
        print(f"  {label}: FAILED - {checkout.stderr.strip()}")
        return False
    if not checkout_is_clean(dest):
        print(f"  {label}: FAILED - pinned checkout has local changes")
        return False
    print(f"  {label}: ready")
    return True


def find_file(filename):
    for path in word_source_candidates(WORDS_DIR, filename):
        if path.is_file():
            return path
    return None


def load_playability(path, max_len=15):
    words = []
    with Path(path).open("r", encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            parts = line.split(None, 1)
            if len(parts) != 2:
                raise ValueError(
                    f"Malformed playability line {line_number}: {line.rstrip()!r}"
                )
            raw_word = parts[1].strip()
            if not raw_word.isascii() or not raw_word.isalpha():
                raise ValueError(
                    f"Invalid playability word on line {line_number}: "
                    f"{raw_word!r}"
                )
            w = raw_word.upper()
            if 2 <= len(w) <= max_len:
                try:
                    words.append((w, int(parts[0])))
                except ValueError as exc:
                    raise ValueError(
                        f"Invalid rank on playability line {line_number}"
                    ) from exc
    return words


def load_full(path, max_len=15):
    words = []
    with Path(path).open("r", encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            parts = line.split()
            if not parts:
                continue
            raw_word = parts[0]
            if not raw_word.isascii() or not raw_word.isalpha():
                raise ValueError(
                    f"Invalid dictionary word on line {line_number}: "
                    f"{raw_word!r}"
                )
            w = raw_word.upper()
            if 2 <= len(w) <= max_len:
                words.append(w)
    return words


def write_dictionary(path, words):
    """Atomically replace the dictionary after writing every validated word."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                newline="\n",
                dir=str(output_path.parent),
                prefix=f".{output_path.name}.",
                suffix=".tmp",
                delete=False) as output_file:
            temporary_path = Path(output_file.name)
            for word in words:
                output_file.write(word + "\n")
        temporary_path.replace(output_path)
    except OSError:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        raise


def main():
    p = argparse.ArgumentParser(description="NWL23 dictionary setup")
    p.add_argument("--output", default="dict.txt")
    p.add_argument("--full", action="store_true", help="Use full 196K list")
    p.add_argument("--max-length", type=int, default=15)
    args = p.parse_args()
    if not 2 <= args.max_length <= 15:
        p.error("--max-length must be between 2 and 15")

    print("Fetching data...")
    if not prepare_words_source(WORDS_REPO, WORDS_DIR, "NWL23 words"):
        sys.exit(1)

    words = set()
    source = None

    if not args.full:
        path = find_file(NWL_PLAYABILITY)
        if path:
            print(f"\nLoading: {path}")
            try:
                ranked = load_playability(path, args.max_length)
            except (OSError, ValueError) as exc:
                p.error(f"could not load playability data: {exc}")
            words = set(w for w, _ in ranked)
            source = f"NWL23-Playability ({len(words)} words)"

    if args.full or not words:
        path = find_file(NWL_FULL)
        if path:
            print(f"\nLoading: {path}")
            try:
                words = set(load_full(path, args.max_length))
            except (OSError, ValueError) as exc:
                p.error(f"could not load full dictionary data: {exc}")
            source = f"NWL23-Full ({len(words)} words)"

    if not words:
        print("\nERROR: No compatible words found in the prepared NWL23 sources")
        sys.exit(1)

    sorted_words = sorted(words)
    output_path = Path(args.output)
    try:
        write_dictionary(output_path, sorted_words)
    except OSError as exc:
        p.error(f"could not write dictionary: {exc}")

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
