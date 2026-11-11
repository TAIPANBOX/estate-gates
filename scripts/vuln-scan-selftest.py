#!/usr/bin/env python3
"""Teeth for scripts/vuln-scan.py: each case plants one fault (or one non-fault)
in a miniature estate and requires the scanner to say so.

WHY THIS IS A SEPARATE FILE AND NOT A PART OF selftest.py

selftest.py proves the gates in gates/, which are dependency-free (python3, bash
and git, invariant 8) and run in a few seconds on a clone of the estate. The
scanner needs real tools and the network: govulncheck with a Go toolchain,
cargo-audit, osv-scanner, pip-audit, and the vulnerability databases behind
them. A case that plants a crate with a known advisory is only worth something
if the real cargo-audit reads it, and a case that plants a Go call into a
vulnerable function is only worth something if the real govulncheck decides it
is reachable. So these cases run where the tools are installed: the
vulnerability scan workflow runs this file first, and the scan only runs if it
passed. Same order as gates.yml, for the same reason: a verdict from a scanner
that has not been shown to find anything is worth nothing.

NAMES ARE BOUND

`CASES` is read by scripts/features-are-bound.sh. A scenario in
features/vuln-scan.feature binds to a case with `@scan:<name>`; a scenario
bound to a name that is not here is DANGLING, and a case with no scenario is
UNWRITTEN.

Each case is run, never skipped. A case that cannot set itself up is a failure.
"""

from __future__ import annotations

import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
SCANNER = HERE / "vuln-scan.py"

CASES = (
    "rust-vulnerable-crate-is-a-finding",
    "go-called-vulnerable-function-is-a-finding",
    "go-imported-but-not-called-is-clean",
    "js-lockfile-vulnerable-package-is-a-finding",
    "py-requirements-vulnerable-pin-is-a-finding",
    "clean-modules-are-clean",
    "nested-lockfiles-are-scanned",
    "no-manifest-and-no-declaration-could-not-measure",
    "declared-no-manifests-is-not-a-finding",
    "declared-none-but-manifests-exist-fails",
    "zero-subjects-scanned-is-not-green",
    "estate-subject-without-a-clone-is-red",
    "subjects-come-from-estate-json",
    "private-repository-is-partial-not-clean",
    "broken-tool-could-not-measure",
    "missing-tool-could-not-measure",
    "wrong-tool-version-could-not-measure",
    "finding-outranks-could-not-measure",
)

CLEAN_GO_MOD = "module example.test/{name}\n\ngo 1.27\n"
CLEAN_MAIN = "package main\n\nfunc main() {{}}\n"

# smallvec, time and the like come and go; these pins have carried an advisory
# for years and are fixed in later releases, so the cases keep their meaning.
#   time 0.1.43       RUSTSEC-2020-0071
#   x/text v0.3.5     GO-2021-0113, symbols language.Parse and friends
#   lodash 4.17.15    GHSA-35jh-r3h4-6jhm and others
#   Django 2.2.0      PYSEC/GHSA records
CARGO_LOCK_BAD = """version = 3

[[package]]
name = "planted"
version = "0.1.0"
dependencies = [
 "time",
]

[[package]]
name = "time"
version = "0.1.43"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "ca8a50ef2360fbd1eeb0ecd46795a87a19024eb4b53c5dc916ca1fd95fe62438"
"""

CARGO_LOCK_CLEAN = """version = 3

[[package]]
name = "planted"
version = "0.1.0"
"""

PACKAGE_LOCK_BAD = {
    "name": "planted",
    "version": "1.0.0",
    "lockfileVersion": 3,
    "requires": True,
    "packages": {
        "": {"name": "planted", "version": "1.0.0", "dependencies": {"lodash": "4.17.15"}},
        "node_modules/lodash": {
            "version": "4.17.15",
            "resolved": "https://registry.npmjs.org/lodash/-/lodash-4.17.15.tgz",
        },
    },
}


def _write(path: pathlib.Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _go_tidy(directory: pathlib.Path) -> None:
    env = dict(os.environ, GOTOOLCHAIN="auto", GOFLAGS="-mod=mod")
    proc = subprocess.run(["go", "mod", "tidy"], cwd=directory, env=env, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"go mod tidy failed in {directory}: {proc.stderr.strip()[-300:]}")


def build_repo(root: pathlib.Path, name: str) -> None:
    """One fixture repository under root. Names say what is planted."""
    d = root / name
    d.mkdir(parents=True, exist_ok=True)
    if name == "goclean":
        _write(d / "go.mod", CLEAN_GO_MOD.format(name=name))
        _write(d / "main.go", CLEAN_MAIN)
    elif name == "gobad":
        _write(d / "go.mod", CLEAN_GO_MOD.format(name=name) + "\nrequire golang.org/x/text v0.3.5\n")
        _write(
            d / "main.go",
            'package main\n\nimport "golang.org/x/text/language"\n\n'
            'func main() { _, _ = language.Parse("en") }\n',
        )
        _go_tidy(d)
    elif name == "goimport":
        # The vulnerable package is imported and the vulnerable function is
        # never called. govulncheck reports nothing for this, and so does the
        # required check in every Go repository, so the night must as well.
        _write(d / "go.mod", CLEAN_GO_MOD.format(name=name) + "\nrequire golang.org/x/text v0.3.5\n")
        _write(
            d / "main.go",
            'package main\n\nimport "golang.org/x/text/language"\n\n'
            "var _ = language.English\n\nfunc main() {}\n",
        )
        _go_tidy(d)
    elif name == "gonested":
        _write(d / "go.mod", CLEAN_GO_MOD.format(name=name))
        _write(d / "main.go", CLEAN_MAIN)
        sub = d / "tools" / "inner"
        _write(sub / "go.mod", CLEAN_GO_MOD.format(name="gonested-inner") + "\nrequire golang.org/x/text v0.3.5\n")
        _write(
            sub / "main.go",
            'package main\n\nimport "golang.org/x/text/language"\n\n'
            'func main() { _, _ = language.Parse("en") }\n',
        )
        _go_tidy(sub)
    elif name == "rustbad":
        # A clean root lockfile and a vulnerable nested one: the nested one
        # must be found, and the clean root must still be reported on its own.
        _write(d / "Cargo.lock", CARGO_LOCK_CLEAN)
        _write(d / "crates" / "inner" / "Cargo.lock", CARGO_LOCK_BAD)
    elif name == "rustclean":
        _write(d / "Cargo.lock", CARGO_LOCK_CLEAN)
    elif name == "jsbad":
        _write(d / "web" / "package-lock.json", json.dumps(PACKAGE_LOCK_BAD, indent=2) + "\n")
    elif name == "pybad":
        _write(d / "requirements.txt", "django==2.2.0\n")
    elif name == "empty":
        _write(d / "README.md", "nothing here that any scanner reads\n")
    elif name == "declared":
        _write(d / "README.md", "declared as having no dependency manifests\n")
    elif name == "lie":
        _write(d / "go.mod", CLEAN_GO_MOD.format(name=name))
        _write(d / "main.go", CLEAN_MAIN)
    else:
        raise RuntimeError(f"no fixture named {name}")


def registry_for(repos: list[str], private: list[str] | None = None) -> dict:
    out: dict = {}
    for name in repos:
        entry: dict = {"github": f"TAIPANBOX/{name}", "local": name, "role": "fixture", "runs": []}
        if name in ("declared", "lie"):
            entry["vuln_scan"] = {"manifests": "none", "why": "a fixture that holds no dependency manifest"}
        out[name] = entry
    for name in private or []:
        out[name] = {
            "github": None,
            "local": name,
            "role": "fixture",
            "runs": [],
            "why_no_remote": "PRIVATE by decision, a fixture",
        }
    return {"repos": out}


STUB_BROKEN = "#!/bin/sh\necho 'boom: the tool cannot start' >&2\nexit 2\n"
# Reports a version that is not the pinned one and then claims there is
# nothing to find. A scanner that took that at its word would print clean for
# every module in the estate.
STUB_WRONG_VERSION = (
    "#!/bin/sh\n"
    'if [ "$1" = "-version" ]; then echo "govulncheck@v0.0.1"; exit 0; fi\n'
    'echo "No vulnerabilities found."\nexit 0\n'
)


class Case:
    def __init__(self, name, repos, expect_exit, must, must_not=(), private=None, extra=None, registry_repos=None, stubs=None):
        self.name = name
        self.repos = repos  # fixture directories present under --root
        self.registry_repos = repos if registry_repos is None else registry_repos
        self.expect_exit = expect_exit
        self.must = must  # regexes, each must match a line
        self.must_not = must_not  # regexes, none may match a line
        self.private = private
        self.extra = extra or []
        self.stubs = stubs or {}


def table() -> dict[str, Case]:
    cs = [
        Case(
            "rust-vulnerable-crate-is-a-finding",
            ["rustbad"],
            1,
            [r"^FINDING\s+rustbad\s+rust\s+crates/inner/Cargo\.lock\s.*RUSTSEC-2020-0071",
             r"^clean\s+rustbad\s+rust\s+Cargo\.lock\b"],
        ),
        Case(
            "go-called-vulnerable-function-is-a-finding",
            ["gobad"],
            1,
            [r"^FINDING\s+gobad\s+go\s+\.\s.*GO-2021-0113"],
            [r"^clean\s+gobad"],
        ),
        Case(
            "go-imported-but-not-called-is-clean",
            ["goimport"],
            0,
            [r"^clean\s+goimport\s+go\s+\."],
            [r"^FINDING"],
        ),
        Case(
            "js-lockfile-vulnerable-package-is-a-finding",
            ["jsbad"],
            1,
            [r"^FINDING\s+jsbad\s+js\s+web/package-lock\.json\s.*lodash@4\.17\.15"],
        ),
        Case(
            "py-requirements-vulnerable-pin-is-a-finding",
            ["pybad"],
            1,
            [r"^FINDING\s+pybad\s+py\s+requirements\.txt\s.*(?i:django)@2\.2\.0"],
        ),
        Case(
            "clean-modules-are-clean",
            ["goclean", "rustclean"],
            0,
            [r"^clean\s+goclean\s+go\s+\.", r"^clean\s+rustclean\s+rust\s+Cargo\.lock",
             r"^OK: every subject was measured and none has a finding"],
            [r"^FINDING", r"^COULD NOT MEASURE"],
        ),
        Case(
            "nested-lockfiles-are-scanned",
            ["gonested"],
            1,
            [r"^clean\s+gonested\s+go\s+\.\s", r"^FINDING\s+gonested\s+go\s+tools/inner\s.*GO-2021-0113"],
        ),
        Case(
            "no-manifest-and-no-declaration-could-not-measure",
            ["empty", "goclean"],
            2,
            [r"^COULD NOT MEASURE\s+empty\s", r"^clean\s+goclean"],
            [r"^OK:"],
        ),
        Case(
            "declared-no-manifests-is-not-a-finding",
            ["declared", "goclean"],
            0,
            [r"^declared\s+declared\s.*no dependency manifest", r"^clean\s+goclean"],
            [r"^FINDING", r"^COULD NOT MEASURE"],
        ),
        Case(
            "declared-none-but-manifests-exist-fails",
            ["lie", "goclean"],
            1,
            [r"^FAIL\s+lie\s.*go\.mod"],
            [r"^OK:"],
        ),
        Case(
            "zero-subjects-scanned-is-not-green",
            ["declared"],
            2,
            [r"measured nothing"],
            [r"^OK:"],
        ),
        Case(
            "estate-subject-without-a-clone-is-red",
            ["goclean"],
            2,
            [r"^COULD NOT MEASURE\s+ghost\s.*no checkout", r"^clean\s+goclean"],
            [r"^OK:"],
            registry_repos=["goclean", "ghost"],
        ),
        Case(
            "subjects-come-from-estate-json",
            ["goclean", "gobad"],
            0,
            [r"^clean\s+goclean"],
            [r"gobad"],
            registry_repos=["goclean"],
        ),
        Case(
            "private-repository-is-partial-not-clean",
            ["goclean"],
            3,
            [r"^NOT MEASURED\s+hidden\s.*PRIVATE", r"^clean\s+goclean", r"PARTIAL"],
            [r"^OK:"],
            private=["hidden"],
        ),
        Case(
            "broken-tool-could-not-measure",
            ["goclean"],
            2,
            [r"^COULD NOT MEASURE\s+goclean\s+go\s"],
            [r"^clean\s+goclean", r"^OK:"],
            extra=["--govulncheck", "@broken"],
            stubs={"@broken": STUB_BROKEN},
        ),
        Case(
            "missing-tool-could-not-measure",
            ["rustclean"],
            2,
            [r"^COULD NOT MEASURE\s+rustclean\s+rust\s"],
            [r"^clean\s+rustclean", r"^OK:"],
            extra=["--cargo-audit", "/nonexistent/cargo-audit"],
        ),
        Case(
            "wrong-tool-version-could-not-measure",
            ["goclean"],
            2,
            [r"^COULD NOT MEASURE\s+goclean\s+go\s.*v0\.0\.1"],
            [r"^clean\s+goclean", r"^OK:"],
            extra=["--govulncheck", "@wrong"],
            stubs={"@wrong": STUB_WRONG_VERSION},
        ),
        Case(
            "finding-outranks-could-not-measure",
            ["gobad", "empty"],
            1,
            [r"^FINDING\s+gobad", r"^COULD NOT MEASURE\s+empty"],
        ),
    ]
    out = {c.name: c for c in cs}
    missing = set(CASES) - set(out)
    extra = set(out) - set(CASES)
    if missing or extra:
        raise SystemExit(f"CASES and table() disagree: missing {sorted(missing)}, extra {sorted(extra)}")
    return out


def run_case(case: Case) -> list[str]:
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        base = pathlib.Path(tmp)
        root = base / "root"
        root.mkdir()
        try:
            for name in case.repos:
                build_repo(root, name)
        except RuntimeError as exc:
            return [f"{case.name}: fixture setup failed, so this case proved nothing: {exc}"]
        # `ghost` is in the registry and in no checkout, on purpose.
        registry = registry_for(case.registry_repos, case.private)
        reg_path = base / "estate.json"
        reg_path.write_text(json.dumps(registry), encoding="utf-8")
        args = [sys.executable, str(SCANNER), "--root", str(root), "--registry", str(reg_path)]
        for a in case.extra:
            if a in case.stubs:
                stub = base / ("stub-" + a.lstrip("@"))
                stub.write_text(case.stubs[a], encoding="utf-8")
                stub.chmod(0o755)
                a = str(stub)
            args.append(a)
        proc = subprocess.run(args, capture_output=True, text=True, timeout=1500)
        out = proc.stdout
        lines = out.splitlines()
        if proc.returncode != case.expect_exit:
            problems.append(
                f"{case.name}: exit {proc.returncode}, wanted {case.expect_exit}\n"
                + "\n".join("      " + ln for ln in (out + proc.stderr).splitlines()[-25:])
            )
        for rx in case.must:
            if not any(re.search(rx, ln) for ln in lines):
                problems.append(f"{case.name}: no line matches /{rx}/")
        for rx in case.must_not:
            hit = next((ln for ln in lines if re.search(rx, ln)), None)
            if hit is not None:
                problems.append(f"{case.name}: a line matches /{rx}/ and must not: {hit.strip()[:140]}")
    return problems


def main(argv: list[str]) -> int:
    if argv[1:] == ["--list"]:
        print("\n".join(CASES))
        return 0
    if not SCANNER.is_file():
        print(f"FAIL: {SCANNER} is not there, so there is nothing to prove.")
        return 1
    cases = table()
    only = [a for a in argv[1:] if not a.startswith("-")]
    chosen = [cases[n] for n in CASES if not only or n in only]
    if not chosen:
        print("FAIL: no case matched, so this run proved nothing.")
        return 1
    bad = 0
    for case in chosen:
        problems = run_case(case)
        if problems:
            bad += 1
            print(f"FAIL {case.name}")
            for p in problems:
                print("     " + p.replace("\n", "\n     "))
        else:
            print(f"ok   {case.name}")
    print()
    if bad:
        print(f"FAIL: {bad} of {len(chosen)} cases did not get the answer they exist to require.")
        return 1
    print(f"OK: {len(chosen)} cases. Each fault is found and each non-fault stays quiet.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
