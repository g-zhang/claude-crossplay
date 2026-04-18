---
name: crossplay-solver
description: Solve NYT Crossplay board positions — find the highest-scoring legal moves given a board screenshot and a rack of tiles. This is a bootstrap skill that clones the latest solver scripts and full skill instructions from GitHub on first use, so it's always up to date. Use this skill whenever the user mentions NYT Crossplay, Crossplay, or shares a screenshot of a Crossplay board and asks what to play, or references rack letters and wants move suggestions. Also use when the user asks dictionary questions like "words ending in Z" or "4 letter words with Q", or asks for hints/ideas on a Crossplay board. This skill handles board reconstruction from images, NWL23 dictionary setup, cross-word validation, premium square scoring, and visual HTML output of recommended plays.
---

# NYT Crossplay Solver — Bootstrap

This is a thin bootstrap skill. It fetches the latest solver scripts from
GitHub and then delegates to the full `crossplay-solver-core` skill
definition that lives in the repo. This way the workflow is always up to
date without reinstalling the skill.

## Step 0: Fetch latest sources (once per session)

Run this once per session. It's idempotent — if the clone already exists,
it is reused.

```bash
SRC=/home/claude/claude-crossplay-src
if [ ! -d "$SRC/.git" ]; then
  git clone --depth 1 --filter=blob:none --sparse \
    https://github.com/g-zhang/claude-crossplay "$SRC" \
    && git -C "$SRC" sparse-checkout set core
fi
```

If the clone fails (e.g. no network access, GitHub unreachable), stop and
tell the user. The solver cannot run without these scripts.

## Step 1: Delegate to the core skill

Read `/home/claude/claude-crossplay-src/core/SKILL.md` and follow its
instructions verbatim for the rest of the task. Wherever that file
references `<SKILL_DIR>`, substitute
`/home/claude/claude-crossplay-src/core`.

That includes mode detection (Dictionary / Hint / Full Solver), the full
6-step solver workflow, board confirmation, scoring rules, and the NWL23
reference module — everything lives in the cloned `core/SKILL.md` and its
`scripts/` directory.

## Bug reporting

When the user reports a bug, asks how to file an issue, or says
something went wrong, help them assemble a report with version info so
the maintainer can trace the exact build. File at:
**https://github.com/g-zhang/claude-crossplay/issues**

Gather both versions — the bootstrap has its own stamped footer, and
the cloned core must be identified via git:

1. **Bootstrap version** — the last line of this `SKILL.md` file is a
   footer stamped at release time, e.g.
   `_Built from `v1.2.3` (`<40-char sha>`) on `2026-04-17`._`.
   Copy it verbatim. If the footer is absent, this is a local/dev
   install — say so.

2. **Core version** — run:
   ```bash
   git -C /home/claude/claude-crossplay-src rev-parse HEAD
   git -C /home/claude/claude-crossplay-src log -1 --format=%cI
   ```
   for the commit SHA and committer timestamp of the cloned `core/`.
   If the directory doesn't exist, the bug occurred before Step 0
   completed — say so instead.

Then present this ready-to-paste template to the user:

```
### Environment
- Skill: crossplay-solver (bootstrap)
- Bootstrap: <footer line verbatim>
- Core (cloned): <sha>  committed <iso-timestamp>

### What I did
<brief description; attach screenshot if relevant>

### What happened
<error message or wrong output>

### What I expected
<…>
```
