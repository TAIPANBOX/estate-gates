#!/usr/bin/env bash
# Every scenario names a finding this repository can actually print, every
# finding a gate can print has a scenario, and every binding points somewhere.
#
# WHY A FINDING ID RATHER THAN A FUNCTION NAME
#
# Elsewhere in the estate a scenario is bound with `@test:` to a Go or Python
# function, and the gate checks the function exists. That is the weaker half of
# what is available here. This repository's unit of proof is the finding id:
# selftest.py holds a table of broken estates, one or more per id, and requires
# the check to go red on each. So an id that exists is an id something has
# already made fail on purpose.
#
# Binding to it therefore gives what a function name cannot: the scenario is
# transitively attached to a fault that has been planted and a red that was
# required.
#
# WHY THREE DIRECTIONS AND NOT TWO
#
#   1. no scenario without a binding      a paragraph proving nothing
#   2. no binding pointing at nothing     worse: it READS as held
#   3. no finding without a scenario      the one this repository needs most
#
# The third exists because of `a-checks-own-subject-list-is-ungated`, which this
# repository was largely built to answer. A feature file listing the behaviours
# somebody remembered is a hand-written subject list with the same failure mode
# as every other one: it is complete on the day it is written and silently
# partial from then on. So the subjects are DISCOVERED from the gate source, the
# same way selftest.py discovers them, and a new finding merged without a
# scenario is red.
#
# WHY NOT A BDD RUNNER
#
# godog, cucumber-rs and pytest-bdd are three runners with three step-definition
# styles across the estate's repositories in three languages, and the value
# asked for is readability: Given/When/Then to read instead of a diff. The
# binding gate delivers that at a fraction of the surface. My engineering call
# and a deviation from a literal reading of "геркін-тести"; overrule it and I
# will wire a real runner.
#
# WHAT THIS DOES NOT DO
#
# It does not check that the fault ASSERTS what the scenario says. Nothing
# mechanical can: the steps are prose and the binding is a pointer, so a
# scenario can drift from its mutation and this stays green. What it catches is
# the pointer breaking and the subject growing, which are the two failures that
# happen on their own.
#
# Run with --prove and it plants each of the three faults in a copy and
# requires itself to find them.
set -uo pipefail

cd "$(git rev-parse --show-toplevel)" || exit 1

python3 - "${1:-}" <<'PY'
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

HERE = pathlib.Path.cwd()
SCENARIO = re.compile(r"^\s*Scenario:\s*(\S.*)$")
BINDING = re.compile(r"@fires:([A-Za-z0-9._-]+)")


def declared_ids(root: pathlib.Path) -> dict[str, str]:
    """Finding ids read out of the gate sources, via selftest.py's own reader.

    Imported rather than reimplemented: two readers of the same fact drift, and
    this repository exists to say so.
    """
    out = subprocess.run(
        [sys.executable, "-c",
         "import selftest, json; print(json.dumps(selftest.declared_red_paths()))"],
        cwd=root, capture_output=True, text=True,
    )
    if out.returncode != 0:
        print("FAIL: could not read the finding ids out of the gates:", file=sys.stderr)
        print(out.stderr.strip()[:600], file=sys.stderr)
        raise SystemExit(1)
    import json
    return json.loads(out.stdout)


def scenarios(root: pathlib.Path) -> list[tuple[str, int, str, list[str]]]:
    """(file, line, title, bindings) for every scenario in features/."""
    found = []
    feat = root / "features"
    for path in sorted(feat.glob("*.feature")):
        pending: list[str] = []
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            hit = BINDING.search(line)
            if hit:
                pending.append(hit.group(1))
                continue
            m = SCENARIO.match(line)
            if m:
                found.append((str(path.relative_to(root)), n, m.group(1).strip(), pending))
                pending = []
    return found


def check(root: pathlib.Path) -> list[str]:
    problems: list[str] = []

    feat = root / "features"
    if not feat.is_dir():
        return ["no features/ directory: nothing to check, and that is not a pass."]

    found = scenarios(root)
    if not found:
        return ["features/ holds no scenario at all, so this measured nothing."]

    declared = declared_ids(root)
    if not declared:
        return ["no finding id could be read out of the gates, so the third "
                "direction measured nothing."]

    bound: set[str] = set()
    for path, line, title, bindings in found:
        if not bindings:
            problems.append(
                f"UNBOUND   {path}:{line}\n"
                f"          {title!r} names no finding, so it proves nothing")
        for b in bindings:
            bound.add(b)
            if b not in declared:
                problems.append(
                    f"DANGLING  {path}:{line}\n"
                    f"          @fires:{b} names a finding no gate can print")

    # Third direction, over this feature file's own subject only: C15 is the
    # manifest check and features/component-manifests.feature is its account.
    # Scoped rather than estate-wide because the other fourteen gates have no
    # feature file yet, and a gate that goes red for work nobody has started is
    # noise rather than a finding.
    for ident, gate in sorted(declared.items()):
        if not ident.startswith("c15."):
            continue
        if ident not in bound:
            problems.append(
                f"UNWRITTEN {gate}\n"
                f"          {ident} can be printed and no scenario describes it")

    return problems


root = HERE

if sys.argv[1:] and sys.argv[1] == "--prove":
    faults = [
        ("a scenario with no binding",
         lambda p: p.write_text(p.read_text().replace(
             "  @fires:c15.nothing-installs-it\n", "", 1), encoding="utf-8"),
         "UNBOUND"),
        ("a binding pointing at nothing",
         lambda p: p.write_text(p.read_text().replace(
             "@fires:c15.nothing-installs-it",
             "@fires:c15.was-renamed-yesterday", 1), encoding="utf-8"),
         "DANGLING"),
        ("a finding with no scenario",
         lambda p: p.write_text(p.read_text().replace(
             "  @fires:c15.probe-disagrees\n", "  ", 1), encoding="utf-8"),
         "UNWRITTEN"),
    ]
    clean = check(root)
    if clean:
        print("FAIL: this repository is not clean, so --prove cannot tell its")
        print("      own planted faults from the ones already here:")
        for p in clean:
            print("      " + p.replace("\n", "\n      "))
        raise SystemExit(1)

    bad = 0
    for name, plant, expect in faults:
        with tempfile.TemporaryDirectory() as d:
            work = pathlib.Path(d) / "estate-gates"
            shutil.copytree(root, work, ignore=shutil.ignore_patterns(
                ".git", ".clones", "__pycache__"))
            target = work / "features" / "component-manifests.feature"
            before = target.read_text(encoding="utf-8")
            plant(target)
            if target.read_text(encoding="utf-8") == before:
                print(f"FAIL: the fault {name!r} changed nothing, so this case")
                print("      proved the check runs, not that it checks.")
                bad += 1
                continue
            got = check(work)
            if not any(p.startswith(expect) for p in got):
                print(f"FAIL: with {name}, this script stayed silent about it.")
                for p in got:
                    print("      " + p.replace("\n", "\n      "))
                bad += 1
            else:
                print(f"ok  {expect:9} {name}")
    if bad:
        raise SystemExit(1)
    print()
    print("OK: 3 cases. Every direction of the binding fails on its own fault.")
    raise SystemExit(0)

problems = check(root)
if problems:
    for p in problems:
        print(p)
    print()
    print(f"FAIL: {len(problems)} problem(s) in the binding between what was")
    print("      asked for and what can be proved.")
    raise SystemExit(1)

found = scenarios(root)
declared = declared_ids(root)
c15 = sum(1 for i in declared if i.startswith("c15."))
print(f"ok  {len(found)} scenario(s), every one bound to a finding a gate can")
print(f"    print, and all {c15} of C15's findings described.")
PY
