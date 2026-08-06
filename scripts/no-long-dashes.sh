#!/usr/bin/env bash
# No long dashes anywhere in this repository: not in code, comments, docs,
# JSON, commit messages or workflow files.
#
# WHY IT IS PYTHON AND NOT GREP
#
# The obvious `grep -P '\x{2014}'` is a trap the estate has already been
# caught by: some grep builds accept the pattern, match nothing, exit 1, and
# read as a clean run. A check that cannot fail is worse than no check, so
# this one decodes the bytes itself and counts. It also prints its own
# verification: run it with --prove and it plants a long dash in a temporary
# file and requires itself to find it.
set -uo pipefail

cd "$(git rev-parse --show-toplevel)" || exit 1

python3 - "${1:-}" <<'PY'
import pathlib
import subprocess
import sys
import tempfile

# Built from its codepoint rather than typed, so this file is not itself the
# one hit every run reports.
EM = chr(0x2014)

SKIP_DIRS = {".git", ".clones", "__pycache__"}


def scan(root: pathlib.Path) -> list[tuple[str, int, str]]:
    hits = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for n, line in enumerate(text.splitlines(), 1):
            if EM in line:
                hits.append((str(path.relative_to(root)), n, line.strip()[:90]))
    return hits


root = pathlib.Path.cwd()

if sys.argv[1:] and sys.argv[1] == "--prove":
    # The check checking itself: a file with one long dash in it must be found.
    with tempfile.TemporaryDirectory(dir=root) as d:
        probe = pathlib.Path(d) / "probe.txt"
        probe.write_text(f"one long dash {EM} here\n", encoding="utf-8")
        found = [h for h in scan(root) if "probe.txt" in h[0]]
    if not found:
        print("FAIL: this script could not find a long dash it planted itself,")
        print("      so a clean report from it means nothing.")
        sys.exit(1)
    print("OK: the planted long dash was found, so a clean report means something.")

hits = scan(root)
if hits:
    for path, n, line in hits:
        print(f"FAIL: {path}:{n} carries a long dash: {line}")
    print()
    print("Use a comma, a colon, parentheses, or a short hyphen. This applies to")
    print("every file in this repository, including the ones nobody reads twice.")
    sys.exit(1)

files = sum(
    1
    for p in root.rglob("*")
    if p.is_file() and not any(part in SKIP_DIRS for part in p.parts)
)
print(f"OK: no long dash in any of the {files} files in this repository.")
PY
