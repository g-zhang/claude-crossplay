# Agent instructions for this repository

Applies to any AI coding agent (Copilot CLI, Claude Code, Cursor, etc.)
and to human contributors.

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

Quick check before committing:

```
python -c "import sys,re;
[print(f) for f in sys.argv[1:]
 if re.search(r'[^\x00-\x7f]', open(f,encoding='utf-8').read())]" \
  $(git diff --cached --name-only --diff-filter=AM | grep -E '\.(py|ps1|sh|js|ts|toml|yaml|yml|json)$')
```
