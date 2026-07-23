#!/usr/bin/env python3
"""Fetch a fresh sparse checkout of the current Crossplay solver core."""

import argparse
import shutil
import subprocess
import tempfile
from pathlib import Path


REPOSITORY = "https://github.com/g-zhang/claude-crossplay"
BRANCH = "main"


def run_git(args):
    """Run git with captured UTF-8 output."""
    return subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def fetch_core(destination):
    """Clone the current core into an absent or empty destination."""
    destination = Path(destination)
    if destination.exists():
        if not destination.is_dir():
            raise ValueError("destination exists and is not a directory")
        if any(destination.iterdir()):
            raise ValueError("destination must be absent or empty")
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)

    clone = run_git([
        "clone",
        "--quiet",
        "--depth", "1",
        "--filter=blob:none",
        "--sparse",
        "--branch", BRANCH,
        REPOSITORY,
        str(destination),
    ])
    if clone.returncode != 0:
        raise RuntimeError(clone.stderr.strip() or "git clone failed")

    sparse = run_git([
        "-C", str(destination), "sparse-checkout", "set", "core",
    ])
    if sparse.returncode != 0:
        raise RuntimeError(
            sparse.stderr.strip() or "git sparse-checkout failed"
        )
    return destination.resolve()


def main():
    parser = argparse.ArgumentParser(
        description="Fetch the current Crossplay solver core"
    )
    parser.add_argument(
        "--destination",
        help="Absent or empty checkout directory; defaults to a new temp directory",
    )
    args = parser.parse_args()

    temporary = args.destination is None
    destination = (
        Path(tempfile.mkdtemp(prefix="crossplay-solver-"))
        if temporary
        else Path(args.destination)
    )
    try:
        source_dir = fetch_core(destination)
    except (OSError, RuntimeError, ValueError) as exc:
        if temporary:
            shutil.rmtree(destination, ignore_errors=True)
        parser.error(str(exc))
    print(source_dir)


if __name__ == "__main__":
    main()
