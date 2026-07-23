---
name: crossplay-solver
description: >-
  Solve NYT Crossplay board positions and answer Crossplay or NWL23 rack and
  word-list questions. Use whenever the user mentions NYT Crossplay or
  Crossplay, provides a Crossplay board screenshot, asks for a best play or a
  hint, or asks a word-game lookup involving rack letters or NWL23. Do not use
  for multiplayer cross-platform compatibility, products merely named
  CrossPlay, unrelated crosswords, or Scrabble boards. Use for a general
  dictionary question only when the user explicitly asks to use a Crossplay
  solver skill. This bootstrap fetches the current solver workflow and scripts
  from GitHub before use.
compatibility: >-
  Requires Python 3.8+, git, outbound HTTPS access to github.com, and a writable
  temporary directory. The fetched core also requires opencv-python and numpy.
---

# NYT Crossplay Solver Bootstrap

Refresh the solver from its source repository, then follow the fetched core
skill. Keeping the bootstrap small lets fixes to board reading, scoring, and
presentation reach users without reinstalling the skill.

## 1. Fetch the current core once per conversation

Identify `<SKILL_DIR>` as this installed `crossplay-solver` directory. Run the
bundled fetcher once:

```text
python "<SKILL_DIR>/scripts/fetch_core.py"
```

The command prints a fresh temporary checkout path. If it fails, stop and show
the reported error instead of running a partial checkout. Do not run the
fetcher again during the same conversation.

## 2. Follow the core skill

Remember the printed path as `<SOURCE_DIR>`. Read
`<SOURCE_DIR>/core/SKILL.md` and follow it for the rest of the task. Substitute
`<SOURCE_DIR>/core` for every `<SKILL_DIR>` reference in that file.

The core skill selects Dictionary, Hint, or Full Solver mode and owns the
complete board-confirmation and solving workflow.

## Report a problem

When the user reports a failure, prepare a reproducible report for
https://github.com/g-zhang/claude-crossplay/issues.

Collect:

1. **Bootstrap version:** Copy the final non-empty `_Built from ..._` footer
   from this file. If it is absent, identify the install as local or
   development.
2. **Fetched core version:** Run:

   ```text
   git -C "<SOURCE_DIR>" rev-parse HEAD
   git -C "<SOURCE_DIR>" log -1 --format=%cI
   ```

   If the checkout does not exist, say the failure happened before the fetch
   completed.
3. **Reproduction details:** Include the prompt, relevant screenshot, exact
   error or incorrect output, and expected behavior.

Use this ready-to-paste structure:

```text
### Environment
- Skill: crossplay-solver (bootstrap)
- Bootstrap: <footer or local/development>
- Core: <commit SHA> committed <ISO timestamp>

### What I did
<steps and screenshot>

### What happened
<error or incorrect output>

### What I expected
<expected behavior>
```
