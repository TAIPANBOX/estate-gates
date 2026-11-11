#!/usr/bin/env python3
"""Known vulnerabilities in the main branch of every repository of the estate.

WHY THIS LIVES HERE

Each repository audits its dependencies on push and on pull request, and a new
advisory is published on no repository's schedule. A vulnerability in a
dependency, or in the Go standard library, stays invisible until somebody
pushes. GO-2026-6859 was found by accident, on a README pull request.

A scheduled workflow in each repository does not fix that. GitHub disables
scheduled workflows in a public repository after 60 days without activity, so
the quiet repositories would stop being checked, silently. This repository is
active every day and already runs a nightly job, and its subject list is
estate.json, so a repository cannot be left out without somebody editing the
registry.

WHAT IT RUNS

The tool each repository already treats as a required check, so a red night
means the next pull request there is red too:

  Go            govulncheck ./... in every go.mod directory, with
                GOTOOLCHAIN=auto so the toolchain line of that go.mod is the
                one that is judged. Reachability applies: an imported package
                whose vulnerable function is never called is not a finding,
                exactly as in the repositories' own CI.
  Rust          cargo-audit over every Cargo.lock, run from the repository
                root so that its own .cargo/audit.toml is the one that applies.
                The accepted advisories, and the reason for each, live there
                and are never copied here. cargo-audit reads the lock file and
                compiles nothing.
  Python        pip-audit. A requirements*.txt or requirements*.lock is read as
                it is. A pyproject.toml with no such file beside it is resolved
                with every extra (pip install --dry-run, nothing is installed)
                and the pinned result is read. uv.lock, poetry.lock and
                Pipfile.lock go to osv-scanner. The `--ignore-vuln` ids a
                repository's own workflow passes to pip-audit are passed here
                too, and printed.
  JavaScript    osv-scanner over package-lock.json, npm-shrinkwrap.json,
                pnpm-lock.yaml and yarn.lock.

Every tool is pinned (PINS below) to the version the repositories use, or the
newest at the time of writing where they use none, and its version is read
before it is trusted. A tool of another version is COULD NOT MEASURE, never a
quiet substitute.

WHAT IT PRINTS, AND WHAT EACH WORD MEANS

  clean              the tool ran, read the subject, and found nothing
  FINDING            the tool found an advisory: ids, package, version, fix
  FAIL               estate.json says a repository has no dependency manifest
                     and it has one; the declaration is stale
  COULD NOT MEASURE  the tool could not run, a clone failed, the repository has
                     no recognised manifest and estate.json does not say so
  declared           estate.json records `vuln_scan: {manifests: none, why}`
                     and the tree confirms it
  NOT MEASURED       a repository with no public remote; never counted clean

There is no list of exceptions in this file, by decision for the first version.
A finding is a finding until the repository that owns it fixes or accepts it in
its own configuration.

EXIT CODES

  0  every subject was measured, nothing was found, nothing is private
  1  at least one finding, or a stale declaration
  2  nothing was found, but something could not be measured, or nothing at all
     was measured. Not a pass.
  3  nothing was found, everything public was measured, and the only subjects
     left are repositories estate.json records as having no public remote.
     CI treats it as success and prints what went unmeasured, as for the gates.

Findings outrank the rest, so a red night about a vulnerability is not hidden
by a tool that also failed.

WHAT IT DOES NOT COVER

Container base images, Terraform provider locks (.terraform.lock.hcl),
vendored C code, and any dependency named in no manifest. A vulnerability that
no database knows yet. A manifest nobody commits. Findings are only as current
as the databases behind the tools on the day of the run.

Standard library only, so it needs nothing installed beyond the four tools.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "gates"))

import _estate as E  # noqa: E402

PINS = {
    "govulncheck": "v1.7.0",
    "cargo-audit": "0.22.2",
    "osv-scanner": "2.7.1",
    "pip-audit": "2.10.1",
}

# Version flags, and the text that must contain the pin.
VERSION_ARGS = {
    "govulncheck": ["-version"],
    "cargo-audit": ["--version"],
    "osv-scanner": ["--version"],
    "pip-audit": ["--version"],
}

SKIP_DIRS = {".git", "node_modules", "target", "vendor", "testdata", ".venv", "venv", "__pycache__", ".terraform"}

CLEAN, FINDING, FAIL, CANNOT, DECLARED, PRIVATE = (
    "clean",
    "FINDING",
    "FAIL",
    "COULD NOT MEASURE",
    "declared",
    "NOT MEASURED",
)

EXIT_FINDING = 1
EXIT_INCOMPLETE = 2
EXIT_PARTIAL_EXPECTED = 3


class Row:
    def __init__(self, repo: str, eco: str, path: str, status: str, detail: str):
        self.repo, self.eco, self.path, self.status, self.detail = repo, eco, path, status, detail

    def line(self) -> str:
        return f"{self.status:<17}  {self.repo}  {self.eco}  {self.path}  {self.detail}"


def tail(text: str, n: int = 2, width: int = 220) -> str:
    lines = [ln.strip() for ln in text.strip().splitlines() if ln.strip()]
    return " | ".join(lines[-n:])[:width] if lines else "no output"


def run(cmd: list[str], cwd: pathlib.Path | None = None, env: dict | None = None, timeout: int = 900):
    """(returncode, stdout, stderr). returncode is None when it never ran."""
    try:
        p = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            env=dict(os.environ, **(env or {})),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired:
        return None, "", f"timed out after {timeout}s: {' '.join(cmd[:3])}"
    except OSError as exc:
        return None, "", f"{type(exc).__name__}: {exc}"


class Tools:
    """The four tools, each found, version-checked once, and then trusted."""

    def __init__(self, paths: dict[str, str]):
        self.paths = paths
        self._ok: dict[str, tuple[bool, str]] = {}

    def get(self, name: str) -> tuple[str | None, str]:
        """(binary, reason). binary is None when the tool cannot be trusted."""
        if name not in self._ok:
            binary = self.paths[name]
            rc, out, err = run([binary] + VERSION_ARGS[name], timeout=60)
            text = (out + "\n" + err).strip()
            pin = PINS[name]
            if rc is None or rc != 0:
                self._ok[name] = (False, f"{name} could not report its version ({tail(text)}), so it is not trusted")
            elif pin not in text:
                self._ok[name] = (False, f"{name} is not the pinned {pin}: it reports {tail(text, 1, 80)!r}")
            else:
                self._ok[name] = (True, f"{name} {pin}")
        ok, reason = self._ok[name]
        return (self.paths[name] if ok else None), reason


# ------------------------------------------------------------------ discovery


def walk(root: pathlib.Path) -> list[str]:
    found = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for f in sorted(filenames):
            found.append(str(pathlib.Path(dirpath, f).relative_to(root)))
    return found


JS_LOCKS = {"package-lock.json", "npm-shrinkwrap.json", "pnpm-lock.yaml", "yarn.lock"}
PY_OSV_LOCKS = {"uv.lock", "poetry.lock", "Pipfile.lock"}
REQ = re.compile(r"^requirements[A-Za-z0-9_.-]*\.(txt|lock)$")


def classify(files: list[str]) -> dict[str, list[str]]:
    by_dir: dict[str, set[str]] = {}
    for f in files:
        d, _, base = f.rpartition("/")
        by_dir.setdefault(d or ".", set()).add(base)
    out: dict[str, list[str]] = {k: [] for k in ("go", "rust", "js", "js_bare", "py_req", "py_osv", "py_proj")}

    def rel(d: str, base: str) -> str:
        return base if d == "." else f"{d}/{base}"

    for d, names in sorted(by_dir.items()):
        if "go.mod" in names:
            out["go"].append(d)
        if "Cargo.lock" in names:
            out["rust"].append(rel(d, "Cargo.lock"))
        locks = sorted(names & JS_LOCKS)
        out["js"] += [rel(d, n) for n in locks]
        if "package.json" in names and not locks:
            out["js_bare"].append(rel(d, "package.json"))
        reqs = sorted(n for n in names if REQ.match(n))
        out["py_req"] += [rel(d, n) for n in reqs]
        osv_locks = sorted(names & PY_OSV_LOCKS)
        out["py_osv"] += [rel(d, n) for n in osv_locks]
        if ("pyproject.toml" in names) and not reqs and not osv_locks:
            out["py_proj"].append(rel(d, "pyproject.toml"))
    return out


def has_any(c: dict[str, list[str]]) -> bool:
    return any(c.values())


# ------------------------------------------------------------------- scanners


def cap(items: list[str], n: int = 6) -> str:
    if len(items) <= n:
        return "; ".join(items)
    return "; ".join(items[:n]) + f"; and {len(items) - n} more"


def scan_go(repo: str, root: pathlib.Path, d: str, tools: Tools) -> Row:
    binary, why = tools.get("govulncheck")
    if binary is None:
        return Row(repo, "go", d, CANNOT, why)
    rc, out, err = run([binary, "./..."], cwd=root / d, env={"GOTOOLCHAIN": "auto", "GOWORK": "off"}, timeout=1200)
    if rc is None:
        return Row(repo, "go", d, CANNOT, err)
    if rc == 0:
        extra = re.search(r"also found (\d+) vulnerabilit", out)
        note = f", plus {extra.group(1)} in imported code that is never called" if extra and int(extra.group(1)) else ""
        return Row(repo, "go", d, CLEAN, f"govulncheck {PINS['govulncheck']}, no called vulnerability{note}")
    if rc == 3:
        found: list[str] = []
        cur = None
        for ln in out.splitlines():
            m = re.match(r"^Vulnerability #\d+: (GO-\d+-\d+)", ln)
            if m:
                cur = {"id": m.group(1), "found": "?", "fixed": "no fix"}
                found.append(cur)
                continue
            if cur is None:
                continue
            m = re.match(r"^\s+Found in: (\S+)", ln)
            if m:
                cur["found"] = m.group(1)
            m = re.match(r"^\s+Fixed in: (\S+)", ln)
            if m:
                cur["fixed"] = m.group(1)
        if not found:
            return Row(repo, "go", d, FINDING, f"govulncheck exited 3 and no id could be read: {tail(out)}")
        texts = [f"{f['id']} {f['found']} (fixed in {f['fixed']})" for f in found]
        return Row(repo, "go", d, FINDING, cap(texts))
    return Row(repo, "go", d, CANNOT, f"govulncheck exited {rc}: {tail(err or out)}")


def scan_rust(repo: str, root: pathlib.Path, lock: str, tools: Tools) -> Row:
    binary, why = tools.get("cargo-audit")
    if binary is None:
        return Row(repo, "rust", lock, CANNOT, why)
    rc, out, err = run([binary, "audit", "--file", lock, "--json"], cwd=root, timeout=600)
    if rc is None:
        return Row(repo, "rust", lock, CANNOT, err)
    try:
        d = json.loads(out)
        vulns = d["vulnerabilities"]
        found = bool(vulns["found"])
        count = int(d["lockfile"]["dependency-count"])
    except (ValueError, KeyError, TypeError):
        return Row(repo, "rust", lock, CANNOT, f"cargo-audit exited {rc} with no report: {tail(err or out)}")
    if count == 0:
        return Row(repo, "rust", lock, CANNOT, "cargo-audit read the lock file and found no package in it: measured nothing")
    ignored = (d.get("settings") or {}).get("ignore") or []
    note = f"; the repo's .cargo/audit.toml accepts {', '.join(ignored)}" if ignored else ""
    if found != (rc == 1) or (not found and rc != 0):
        return Row(repo, "rust", lock, CANNOT, f"cargo-audit exited {rc} but its report says found={found}")
    if found:
        texts = []
        for v in vulns.get("list") or []:
            adv, pkg = v.get("advisory", {}), v.get("package", {})
            patched = ", ".join((v.get("versions") or {}).get("patched") or []) or "no fix"
            texts.append(f"{adv.get('id', '?')} {pkg.get('name', '?')}@{pkg.get('version', '?')} (fixed in {patched})")
        return Row(repo, "rust", lock, FINDING, cap(texts) + note)
    warns = d.get("warnings") or {}
    n_warn = sum(len(v) for v in warns.values() if isinstance(v, list))
    wnote = f", {n_warn} warning(s) that do not fail a build" if n_warn else ""
    return Row(repo, "rust", lock, CLEAN, f"cargo-audit {PINS['cargo-audit']}, {count} crates{wnote}{note}")


def osv_rows(repo: str, eco: str, root: pathlib.Path, lock: str, tools: Tools) -> Row:
    binary, why = tools.get("osv-scanner")
    if binary is None:
        return Row(repo, eco, lock, CANNOT, why)
    rc, out, err = run([binary, "scan", "source", "-L", str(root / lock), "--format", "json"], cwd=root, timeout=600)
    if rc is None:
        return Row(repo, eco, lock, CANNOT, err)
    if rc == 128:
        return Row(repo, eco, lock, CANNOT, f"osv-scanner found no package in the file: measured nothing ({tail(err)})")
    if rc not in (0, 1):
        return Row(repo, eco, lock, CANNOT, f"osv-scanner exited {rc}: {tail(err or out)}")
    try:
        d = json.loads(out)
        results = d["results"]
    except (ValueError, KeyError, TypeError):
        return Row(repo, eco, lock, CANNOT, f"osv-scanner exited {rc} with no readable report: {tail(err or out)}")
    texts = []
    for r in results:
        for p in r.get("packages") or []:
            vids = sorted({v["id"] for v in p.get("vulnerabilities") or []})
            if vids:
                pk = p["package"]
                texts.append(f"{pk['name']}@{pk['version']}: {cap(vids, 5)}")
    scanned = re.search(r"found (\d+) packages", err)
    count = scanned.group(1) if scanned else "?"
    if texts:
        if rc != 1:
            return Row(repo, eco, lock, CANNOT, f"osv-scanner exited {rc} but its report lists findings")
        return Row(repo, eco, lock, FINDING, cap(texts, 8))
    if rc != 0:
        return Row(repo, eco, lock, CANNOT, f"osv-scanner exited {rc} and its report lists nothing")
    return Row(repo, eco, lock, CLEAN, f"osv-scanner {PINS['osv-scanner']}, {count} packages")


def pip_ignores(root: pathlib.Path) -> list[str]:
    """The ids a repository's own workflow passes to pip-audit, read from it."""
    ids: list[str] = []
    wf = root / ".github" / "workflows"
    if wf.is_dir():
        for f in sorted(wf.iterdir()):
            if f.suffix in (".yml", ".yaml"):
                for ln in f.read_text(encoding="utf-8", errors="replace").splitlines():
                    if "pip-audit" in ln and not ln.lstrip().startswith("#"):
                        ids += re.findall(r"--ignore-vuln[ =]+([A-Za-z0-9-]+)", ln)
    return sorted(set(ids))


def audit_requirements(repo: str, root: pathlib.Path, reqfile: pathlib.Path, label: str, tools: Tools, source: str) -> Row:
    binary, why = tools.get("pip-audit")
    if binary is None:
        return Row(repo, "py", label, CANNOT, why)
    ignores = pip_ignores(root)
    cmd = [binary, "-r", str(reqfile), "--no-deps", "--disable-pip", "-f", "json", "--progress-spinner", "off"]
    for i in ignores:
        cmd += ["--ignore-vuln", i]
    rc, out, err = run(cmd, cwd=root, timeout=600)
    if rc is None:
        return Row(repo, "py", label, CANNOT, err)
    try:
        deps = json.loads(out)["dependencies"]
    except (ValueError, KeyError, TypeError):
        return Row(repo, "py", label, CANNOT, f"pip-audit exited {rc} with no readable report: {tail(err or out)}")
    skipped = [d["name"] for d in deps if "skip_reason" in d]
    audited = [d for d in deps if "vulns" in d]
    if not audited:
        return Row(repo, "py", label, CANNOT, f"pip-audit audited no package: measured nothing ({tail(err)})")
    if skipped:
        return Row(repo, "py", label, CANNOT, f"pip-audit could not audit {cap(skipped, 4)}")
    note = f"; the repo's own workflow accepts {', '.join(ignores)}" if ignores else ""
    texts = []
    for d in audited:
        for v in d["vulns"]:
            fixes = ", ".join(v.get("fix_versions") or []) or "no fix"
            texts.append(f"{v['id']} {d['name']}@{d['version']} (fixed in {fixes})")
    if texts:
        return Row(repo, "py", label, FINDING, cap(texts, 8) + note)
    return Row(repo, "py", label, CLEAN, f"pip-audit {PINS['pip-audit']}, {len(audited)} packages ({source}){note}")


def scan_py_req(repo: str, root: pathlib.Path, rel: str, tools: Tools) -> Row:
    return audit_requirements(repo, root, root / rel, rel, tools, "as pinned in the file")


def scan_py_proj(repo: str, root: pathlib.Path, rel: str, tools: Tools) -> Row:
    """A pyproject with nothing pinned beside it: resolve everything, install nothing."""
    try:
        import tomllib

        meta = tomllib.loads((root / rel).read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return Row(repo, "py", rel, CANNOT, f"{rel} could not be read: {type(exc).__name__}: {exc}")
    project = meta.get("project") or {}
    deps = project.get("dependencies") or []
    extras = sorted((project.get("optional-dependencies") or {}).keys())
    if not project:
        return Row(repo, "py", rel, CANNOT, f"{rel} has no [project] table, so nothing is declared to scan")
    if not deps and not extras:
        return Row(repo, "py", rel, CLEAN, "declares no dependencies, read from pyproject.toml")
    name = re.sub(r"[-_.]+", "-", str(project.get("name", ""))).lower()
    d = (root / rel).parent
    spec = str(d) + (f"[{','.join(extras)}]" if extras else "")
    with tempfile.TemporaryDirectory() as tmp:
        report = pathlib.Path(tmp) / "report.json"
        rc, out, err = run(
            [sys.executable, "-m", "pip", "install", "--dry-run", "--ignore-installed", "--quiet", "--report", str(report), spec],
            cwd=root,
            env={"PIP_DISABLE_PIP_VERSION_CHECK": "1"},
            timeout=900,
        )
        if rc is None or rc != 0 or not report.is_file():
            return Row(repo, "py", rel, CANNOT, f"pip could not resolve the dependencies (extras {', '.join(extras) or 'none'}): {tail(err or out)}")
        pinned = []
        for item in json.loads(report.read_text(encoding="utf-8")).get("install") or []:
            md = item.get("metadata") or {}
            if re.sub(r"[-_.]+", "-", str(md.get("name", ""))).lower() == name:
                continue
            pinned.append(f"{md['name']}=={md['version']}")
        if not pinned:
            return Row(repo, "py", rel, CANNOT, "pip resolved no dependency: measured nothing")
        req = pathlib.Path(tmp) / "requirements.txt"
        req.write_text("\n".join(sorted(pinned)) + "\n", encoding="utf-8")
        source = f"resolved with extras {', '.join(extras) or 'none'}, nothing installed"
        return audit_requirements(repo, root, req, rel, tools, source)


def scan_js_bare(repo: str, root: pathlib.Path, rel: str) -> Row:
    try:
        pkg = json.loads((root / rel).read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return Row(repo, "js", rel, CANNOT, f"{rel} could not be read: {type(exc).__name__}: {exc}")
    declared = [k for k in ("dependencies", "devDependencies", "optionalDependencies", "peerDependencies") if pkg.get(k)]
    if declared:
        return Row(repo, "js", rel, CANNOT, f"declares {', '.join(declared)} and has no lock file beside it, so nothing is pinned to scan")
    return Row(repo, "js", rel, CLEAN, "declares no dependencies, read from package.json")


# ----------------------------------------------------------------- repository


def scan_repo(repo: str, root: pathlib.Path, entry: dict, tools: Tools) -> list[Row]:
    c = classify(walk(root))
    declared = (entry.get("vuln_scan") or {}).get("manifests") == "none"
    if declared:
        if has_any(c):
            found = sorted(
                {(f"{p}/go.mod" if p != "." else "go.mod") if k == "go" else p for k, v in c.items() for p in v}
            )
            return [
                Row(
                    repo,
                    "-",
                    "-",
                    FAIL,
                    f"estate.json declares no dependency manifest and this repository has {cap(found, 4)}: the declaration is stale",
                )
            ]
        why = (entry.get("vuln_scan") or {}).get("why", "no reason recorded")
        return [Row(repo, "-", "-", DECLARED, f"no dependency manifest, as estate.json records ({why})")]
    if not has_any(c):
        return [
            Row(
                repo,
                "-",
                "-",
                CANNOT,
                "no recognised dependency manifest, and estate.json does not record that it has none "
                "(vuln_scan: manifests none, with a why)",
            )
        ]
    rows: list[Row] = []
    for d in c["go"]:
        rows.append(scan_go(repo, root, d, tools))
    for lock in c["rust"]:
        rows.append(scan_rust(repo, root, lock, tools))
    for rel in c["py_req"]:
        rows.append(scan_py_req(repo, root, rel, tools))
    for rel in c["py_proj"]:
        rows.append(scan_py_proj(repo, root, rel, tools))
    for rel in c["py_osv"]:
        rows.append(osv_rows(repo, "py", root, rel, tools))
    for rel in c["js"]:
        rows.append(osv_rows(repo, "js", root, rel, tools))
    for rel in c["js_bare"]:
        rows.append(scan_js_bare(repo, root, rel))
    return rows


def head(root: pathlib.Path) -> str:
    rc, out, _ = run(["git", "-C", str(root), "rev-parse", "--short", "HEAD"], timeout=30)
    return out.strip() if rc == 0 and out.strip() else "no git head"


def summary_markdown(rows: list[Row], elapsed: float, code: int) -> str:
    verdict = {0: "clean", 1: "FINDINGS", 2: "NOT COMPLETE", 3: "clean, partial (private repositories not measured)"}[code]
    lines = [f"## Vulnerability scan: {verdict}", "", f"{len(rows)} rows in {elapsed:.0f}s.", ""]
    lines += ["| result | repository | ecosystem | path | detail |", "|---|---|---|---|---|"]
    order = {FINDING: 0, FAIL: 0, CANNOT: 1, PRIVATE: 2, DECLARED: 3, CLEAN: 4}
    for r in sorted(rows, key=lambda r: (order[r.status], r.repo, r.path)):
        detail = r.detail.replace("|", "\\|")
        lines.append(f"| {r.status} | {r.repo} | {r.eco} | `{r.path}` | {detail} |")
    return "\n".join(lines) + "\n"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--root", help="directory holding a checkout per repository (default: fresh shallow clones of main)")
    p.add_argument("--cache", help="where fresh clones go (default: a temporary directory)")
    p.add_argument("--registry", help="path to estate.json (default: this repository's own)")
    p.add_argument("--only", action="append", help="scan only this repository (repeatable); for development, a run with it is not the estate")
    for name in PINS:
        p.add_argument(f"--{name}", default=name, help=f"path to {name} (pinned {PINS[name]})")
    args = p.parse_args()

    registry = E.load_registry(pathlib.Path(args.registry) if args.registry else None)
    if args.root:
        estate = E.Estate(registry, mode="worktree", root=pathlib.Path(args.root))
    else:
        cache = pathlib.Path(args.cache) if args.cache else pathlib.Path(tempfile.mkdtemp(prefix="vuln-scan-"))
        estate = E.Estate(registry, mode="clone", cache=cache)
    tools = Tools({name: getattr(args, name.replace("-", "_")) for name in PINS})

    repos = sorted(estate.repos)
    if args.only:
        unknown = [r for r in args.only if r not in estate.repos]
        if unknown:
            print(f"FAIL: --only names {', '.join(unknown)}, which estate.json does not know.")
            return EXIT_FINDING
        repos = [r for r in repos if r in args.only]

    print("=" * 78)
    print("TAIPANBOX estate, known vulnerabilities in main")
    print(f"Source: {estate.label()}")
    print("Tools: " + ", ".join(f"{n} {PINS[n]}" for n in PINS))
    if args.only:
        print(f"ONLY {', '.join(repos)}: this is not a run over the estate.")
    print("=" * 78)

    started = time.time()
    rows: list[Row] = []
    for repo in repos:
        entry = estate.repos[repo]
        try:
            root = estate.dir_of(repo)
        except E.Unavailable as u:
            if entry.get("github"):
                new = [Row(repo, "-", "-", CANNOT, f"the repository could not be read: {u.reason}")]
            else:
                new = [Row(repo, "-", "-", PRIVATE, entry.get("why_no_remote") or u.reason)]
        else:
            print(f"-- {repo} @ {head(root)}")
            new = scan_repo(repo, root, entry, tools)
        for r in new:
            print(r.line())
            sys.stdout.flush()
        rows += new

    elapsed = time.time() - started
    count = {s: sum(1 for r in rows if r.status == s) for s in (CLEAN, FINDING, FAIL, CANNOT, DECLARED, PRIVATE)}
    measured = count[CLEAN] + count[FINDING]
    print()
    print("=" * 78)
    print(
        f"SUMMARY  ({elapsed:.0f}s)  {len(repos)} repositories, {measured} subjects measured: "
        f"{count[CLEAN]} clean, {count[FINDING]} with findings"
    )
    if count[FAIL]:
        print(f"{count[FAIL]} stale declaration(s) in estate.json.")
    if count[CANNOT]:
        print(f"{count[CANNOT]} subject(s) COULD NOT BE MEASURED. That is not a pass.")
    if count[DECLARED]:
        print(f"{count[DECLARED]} repository/ies declared to hold no dependency manifest, each confirmed by the tree.")
    private = [r.repo for r in rows if r.status == PRIVATE]
    if private:
        print(f"PARTIAL: {len(private)} repository/ies with no public remote were not measured: {', '.join(private)}.")

    if count[FINDING] or count[FAIL]:
        code = EXIT_FINDING
        print("Each FINDING line names the advisory, the package and the version that fixes it. The fix, or the")
        print("decision to accept it, belongs in the repository that owns it, in its own configuration.")
    elif count[CANNOT]:
        code = EXIT_INCOMPLETE
        print("No finding in what was measured, and something was not. Nothing here reports clean about a subject it never read.")
    elif measured == 0:
        code = EXIT_INCOMPLETE
        print("FAIL: this run measured nothing. Zero findings over zero scanned subjects is not a clean estate.")
    elif private:
        code = EXIT_PARTIAL_EXPECTED
        print("No finding in what was measured. The private repositories above are the expected partial, and it is not a pass for them.")
    else:
        code = 0
        print("OK: every subject was measured and none has a finding.")

    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(summary_markdown(rows, elapsed, code))
    return code


if __name__ == "__main__":
    sys.exit(main())
