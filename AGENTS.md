# Agent instructions for this repository

Applies to any AI coding agent (Copilot CLI, Claude Code, Cursor, etc.)
and to human contributors.

## Repository layout

This repository ships two Anthropic Agent Skills:

- `src/` is the bootstrap skill (`crossplay-solver`). It fetches the
  current core skill from GitHub so workflow fixes reach users without a
  reinstall.
- `core/` is the solver skill (`crossplay-solver-core`): the workflow in
  `SKILL.md`, `scripts/`, and `references/`.

Tagging `v*` builds `crossplay-solver.skill` and
`crossplay-solver-core.skill` and attaches them to a release.

The automated tests live in a separate private repository. Pushing to
`main` here dispatches a run there that checks out this repo's `core/`
and `src/` and runs its suite against them. A behavior change here needs
its matching test change landed in that repo, so land the public change
first: the private run defaults to public `main`.

## Cross-platform

Code must work on both **Windows** and **Linux**:

- Use stdlib path/subprocess abstractions (`pathlib.Path`,
  `subprocess.run([...])` with a list arg, `shutil`, `tempfile`). Avoid
  `shell=True` and `bash`/`sh`/`pwsh`-only constructs inside scripts.
- Never hard-code path separators. Build paths with `Path` or
  `os.path.join`, not string concatenation with `/` or `\`.
- Open files with explicit text mode and encoding, e.g.
  `open(path, "w", encoding="utf-8")`. The default encoding on Windows
  is cp1252 and will silently mangle non-ASCII output.
- Tests and regression scripts must run the same way on both OSes.
  Mark and skip any OS-specific test on the other platform.

Human-facing docs (README.md, markdown in test/) may show PowerShell
and bash examples side by side. The underlying code stays portable.

## ASCII-only in code and scripts

Source code and scripts use plain ASCII only. This includes .py, .ps1,
.sh, .js, .ts, and config files (TOML, YAML, JSON), along with all
string literals, log messages, and CLI output inside them.

Forbidden: emoji, em/en dashes (U+2014, U+2013), smart quotes, arrows
(U+2192 etc.), bullets (U+2022), ellipsis (U+2026), and any other
non-ASCII character. Use `--`, `-`, `'`, `"`, `->`, `*`, `...`.

Rationale: Windows consoles default to cp1252 and frequently corrupt
non-ASCII output. ASCII-only also keeps diffs clean and grep-friendly.

Exceptions:

- Markdown docs (`*.md`) targeted at humans may use Unicode sparingly,
  but still avoid emoji.
- HTML output files are UTF-8; the template source that emits them
  must still be ASCII.

## Editing a SKILL.md

These follow Anthropic's skill-creator guidance
(https://github.com/anthropics/skills/tree/main/skills/skill-creator).

**Frontmatter.** Only `name`, `description`, `license`, `allowed-tools`,
`metadata`, and `compatibility` are allowed. `name` is kebab-case, at
most 64 characters, and matches the packaged directory name.
`description` is at most 1024 characters and cannot contain `<` or `>`;
`compatibility` is at most 500. CI enforces all of this through
`.github/scripts/validate_skills.rb`, so run it before pushing.

**The description is the trigger.** It is the only part always in
context, so it carries both what the skill does and when to use it. Put
trigger conditions there rather than in the body, phrase it as "Use this
when...", and keep it concrete: models tend to under-trigger skills, so
name the situations that should invoke it, including near-misses that
should not. Aim well under the limit, roughly 100-200 words.

**Progressive disclosure.** The body loads whenever the skill triggers,
so keep `SKILL.md` under about 500 lines and move detail into
`references/`, which loads only on demand. Point to those files from the
body and say when to read them. Give a reference file over ~300 lines a
table of contents. Keep links one level deep from `SKILL.md`.

**Bundled resources.** `scripts/` is executable code for deterministic
or repetitive work, `references/` is documentation read as needed, and
`assets/` is files used in output. Prefer moving repeated multi-step
work into a script so each run does not reinvent it. Scripts should
document their dependencies, degrade gracefully when an optional tool is
missing, and explain failures rather than exiting silently.

**Style.** Write instructions in the imperative, and explain why a step
matters instead of leaning on emphatic MUSTs; all-caps ALWAYS and NEVER
are a signal to reframe. Prefer general guidance over rules fitted to
one example, and drop anything not earning its place. Avoid pinning to
transient versions or dates in the body.

Packaging excludes `__pycache__/`, `node_modules/`, `*.pyc`,
`.DS_Store`, and a top-level `evals/`, so keep anything else out of the
skill directories.

## Before you commit

Run these against staged changes; CI runs the first one and the private
suite, but the rest catch problems earlier.

- Frontmatter: `ruby .github/scripts/validate_skills.rb`
- Whitespace: `git diff --cached --check`
- Python parses:

```
python -c "import ast,pathlib,sys;
[ast.parse(pathlib.Path(p).read_text(encoding='utf-8'), filename=p)
 for p in sys.argv[1:]]" \
  $(git diff --cached --name-only --diff-filter=AM | grep -E '\.py$')
```

- ASCII-only, per the rule above:

```
python -c "import sys,re;
[print(f) for f in sys.argv[1:]
 if re.search(r'[^\x00-\x7f]', open(f,encoding='utf-8').read())]" \
  $(git diff --cached --name-only --diff-filter=AM | grep -E '\.(py|rb|ps1|sh|js|ts|toml|yaml|yml|json)$')
```

A change to rendered HTML or script behavior also needs its matching
test change in the private repository.
