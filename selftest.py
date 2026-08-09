#!/usr/bin/env python3
"""Prove every check in this repository can go red.

THIS IS THE POINT OF THE REPOSITORY

A check that cannot fail is worse than no check, because it reports green
forever and somebody trusts it. The estate got into its current state with
sixteen repositories of good per-repo gates, every one of them green, while
seven of nine wire strings, three weeks of schema drift and a whole
unregistered event source sat between them unnoticed.

So: nothing here is allowed to be a label. Every path in every gate that can
print FAIL has a mutation below that makes it print FAIL, and the AST of the
gate modules is read to guarantee no such path exists without one.

HOW IT WORKS

`selftest/fixture.py` describes a miniature estate, small enough to read in
one sitting and wired so all six checks agree. This script materialises it as
real git repositories in a temporary directory, proves the six pass, then
applies one mutation at a time to a fresh copy and requires the matching
finding to fire.

Three properties of the checks are proved, and they are not the same
property:

  1. THE BASELINE IS GREEN. A check that is always red is as useless as one
     that is always green, and rather more annoying.
  2. EACH RED PATH FIRES. One mutation per finding ID.
  3. NO RED PATH IS UNCOVERED. The finding IDs are read out of the gates with
     ast, so a new FAIL added tomorrow without a mutation fails this script
     rather than joining the suite unexamined. A mutation left behind for a
     finding that no longer exists fails it too.

And one more that belongs to rule 2 rather than rule 1:

  4. AN UNREADABLE REPOSITORY IS NOT A PASS. A repo estate.json records as
     having no public remote is removed, and the run must come back PARTIAL
     with the repo named, never clean.
  5. THE EXIT CODES ARE REAL. All four of run-gates.py's exit codes are
     produced by an actual run. Until this was written, exit 3 had never once
     been returned by anything, because every real run so far also found
     drift, and CI reads the exit code and nothing else.

WHAT THIS DOES NOT PROVE

That the fixture still looks like the real estate. It cannot: the fixture is
written here and the real anchors live in sixteen other repositories. What
catches an anchor going stale there is the nightly run against the real
estate, where an anchor that stops matching is a FAIL by construction. This
script proves the machinery; the nightly run proves the aim.

Needs nothing but python3 and git. Takes a couple of seconds.
"""

from __future__ import annotations

import ast
import io
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "gates"))
sys.path.insert(0, str(HERE / "selftest"))

import _estate as E  # noqa: E402
import fixture  # noqa: E402

GATE_FILES = [
    "c1-pin-currency.py",
    "c2-vendored-schemas.py",
    "c3-mirrored-constants.py",
    "c4-event-registry.py",
    "c5-deployment-parity.py",
    "c6-chain-vectors.py",
]


# --------------------------------------------------------- building the estate


def git(repo: pathlib.Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        env={
            "PATH": "/usr/bin:/bin:/usr/local/bin",
            "HOME": str(repo),
            "GIT_AUTHOR_NAME": "estate-gates selftest",
            "GIT_AUTHOR_EMAIL": "selftest@localhost",
            "GIT_COMMITTER_NAME": "estate-gates selftest",
            "GIT_COMMITTER_EMAIL": "selftest@localhost",
        },
    )


def build_estate(root: pathlib.Path) -> None:
    """Materialise selftest/fixture.py into real git repositories."""
    for repo, files in fixture.ESTATE.items():
        d = root / repo
        d.mkdir(parents=True)
        for relpath, contents in files.items():
            if relpath.startswith("_"):
                continue
            p = d / relpath
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(contents, encoding="utf-8")
        git(d, "init", "--quiet", "-b", "main")
        git(d, "add", "-A")
        git(d, "commit", "--quiet", "-m", "fixture")
        for tag in files.get("_tags", []):
            git(d, "tag", tag)


def fresh_copy(source: pathlib.Path, work: pathlib.Path, n: int) -> pathlib.Path:
    dest = work / f"case{n}"
    shutil.copytree(source, dest)
    return dest


def run_checks(
    root: pathlib.Path, registry: pathlib.Path, expectations: pathlib.Path
) -> tuple[dict[str, str], list[str], str]:
    """Run all six gates against `root`.

    Returns (finding id -> worst verdict seen, per-check verdicts, full text).
    """
    import importlib.util
    import os

    os.environ["ESTATE_GATES_EXPECTATIONS"] = str(expectations)
    estate = E.Estate(
        json.loads(registry.read_text(encoding="utf-8")),
        mode="worktree",
        root=root,
    )
    seen: dict[str, str] = {}
    verdicts: list[str] = []
    buffer = io.StringIO()
    for name in GATE_FILES:
        path = HERE / "gates" / name
        spec = importlib.util.spec_from_file_location(name.replace("-", "_")[:-3], path)
        module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        spec.loader.exec_module(module)  # type: ignore[union-attr]
        check = module.run(estate)
        for kind, ident, _msg, _detail in check.findings:
            if kind in (E.DRIFT, E.MISSING):
                seen[ident] = E.DRIFT
            else:
                seen.setdefault(ident, kind)
        verdicts.append(f"{check.key}={check.verdict()}")
        check.render(buffer)
    return seen, verdicts, buffer.getvalue()


def run_runner(
    root: pathlib.Path,
    registry: pathlib.Path,
    expectations: pathlib.Path,
    only: str | None = None,
) -> int:
    """`run-gates.py` as a subprocess, for its exit code and nothing else."""
    import os

    args = [
        sys.executable,
        str(HERE / "run-gates.py"),
        "--root",
        str(root),
        "--registry",
        str(registry),
    ]
    if only:
        args += ["--only", only]
    env = dict(os.environ, ESTATE_GATES_EXPECTATIONS=str(expectations))
    return subprocess.run(args, capture_output=True, text=True, env=env).returncode


def fired(seen: dict[str, str], ident: str) -> bool:
    """Whether a red finding with this ID (or this ID plus a `:subject`
    suffix) was reported."""
    for key, kind in seen.items():
        if kind != E.DRIFT:
            continue
        if key == ident or key.startswith(ident + ":"):
            return True
    return False


# -------------------------------------------------------------- the mutations
#
# One entry per finding ID a gate can print FAIL with, and a LIST of broken
# estates per entry, because one case per ID is not enough where a check ANDs
# or claims to be stricter than the obvious comparison.
#
# That lesson is borrowed and then paid for again. bank-in-a-box learned it as
# "where a check ANDs, so must the mutations". This script learned the second
# half of it the hard way: C2's single mutation renamed a FIELD, so rewriting
# C2 to compare tokens instead of bytes (`copy.split() == canonical.split()`)
# left every mutation firing and the self-test green, while the check had
# quietly stopped enforcing the byte-identity its own docstring argues for. A
# mutation that a WEAKENED check still catches proves the check runs, not that
# it checks. Hence the whitespace-only case beside the field-rename one, and
# the same treatment wherever a comparison has more than one way to be wrong.
#
# Where a mutation trips a second finding as well, that is fine and expected:
# the requirement is that this mutation makes THIS finding fire, not that it
# makes only this one fire.


def edit(root: pathlib.Path, rel: str, old: str, new: str, every: bool = False) -> None:
    """Replace the first occurrence, or all of them with `every`.

    `every` matters more than it looks. Renaming ONE of five constants a check
    collects leaves the check reading four and reporting a difference rather
    than an unreadable mirror, so the mutation proves the wrong finding. Each
    use of `every` below is a case where that happened.
    """
    p = root / rel
    text = p.read_text(encoding="utf-8")
    if old not in text:
        raise AssertionError(
            f"selftest mutation is stale: {old!r} is not in {rel}. The fixture "
            f"changed under a mutation, so that mutation proves nothing."
        )
    p.write_text(text.replace(old, new, -1 if every else 1), encoding="utf-8")


def drop(root: pathlib.Path, rel: str) -> None:
    p = root / rel
    if not p.exists():
        raise AssertionError(f"selftest mutation is stale: {rel} is not in the fixture")
    p.unlink()


def gomod_pin(root: pathlib.Path, repo: str, pin: str) -> None:
    edit(root, f"{repo}/go.mod", "agent-stack-go v0.5.1", f"agent-stack-go {pin}")


MUTATIONS: dict[str, list[tuple[str, callable]]] = {
    # ---- C1
    "c1.no-tags": [(
        "agent-stack-go has no tags",
        lambda r: git(r / "agent-stack-go", "tag", "-d", "v0.1.0", "v0.5.1"),
    )],
    "c1.repo-unreadable": [(
        "a consumer's directory is not a git repo",
        lambda r: shutil.rmtree(r / "qryx" / ".git"),
    )],
    "c1.gomod-vanished": [(
        "go.mod is in the index and gone from disk",
        lambda r: drop(r, "qryx/go.mod"),
    )],
    "c1.require-unparsed": [(
        "go.mod names the module with no require line",
        lambda r: edit(
            r,
            "qryx/go.mod",
            "require github.com/TAIPANBOX/agent-stack-go v0.5.1",
            "// see github.com/TAIPANBOX/agent-stack-go",
        ),
    )],
    "c1.replace-directive": [(
        "a replace points the module at a local path",
        lambda r: (r / "qryx" / "go.mod").write_text(
            (r / "qryx" / "go.mod").read_text()
            + "\nreplace github.com/TAIPANBOX/agent-stack-go => ../agent-stack-go\n"
        ),
    )],
    "c1.no-consumers": [(
        "no repository requires the module at all",
        lambda r: [
            edit(r, f"{repo}/go.mod", "require github.com/TAIPANBOX/agent-stack-go v0.5.1", "")
            for repo in ("idryx", "qryx", "wardryx", "mockryx", "heraldyx",
                         "terraform-provider-taipan")
        ],
    )],
    "c1.unparseable-pin": [(
        "a consumer pins a pseudo-version",
        lambda r: gomod_pin(r, "qryx", "v0.0.0-20260101000000-abcdef123456"),
    )],
    "c1.ahead-of-module": [(
        "a consumer pins ahead of the newest tag",
        lambda r: gomod_pin(r, "qryx", "v9.9.9"),
    )],
    "c1.minor-behind": [(
        "a consumer is a minor behind",
        lambda r: gomod_pin(r, "qryx", "v0.1.0"),
    )],
    "c1.patch-behind": [(
        "a consumer is a patch behind",
        lambda r: gomod_pin(r, "qryx", "v0.5.0"),
    )],
    # ---- C2
    "c2.canonical-gone": [(
        "the canonical schema is deleted",
        lambda r: drop(r, "agent-passport/schemas/agent-event.schema.json"),
    )],
    "c2.copy-gone": [(
        "a vendored copy is deleted",
        lambda r: drop(r, "engram/tests/fixtures/agent-event.v0.2.schema.json"),
    )],
    "c2.bytes-differ": [
        (
            "a vendored copy differs by one field",
            lambda r: edit(
                r,
                "genaryx/crates/core/src/schemas/agent-event.v0.2.schema.json",
                '"prev_hash"',
                '"previous_hash"',
            ),
        ),
        (
            # The case that catches C2 being rewritten to compare tokens or
            # parsed JSON instead of bytes. Nothing about this copy's MEANING
            # changed, and C2 claims to fail on it anyway.
            "a vendored copy differs only in whitespace",
            lambda r: edit(
                r,
                "genaryx/crates/core/src/schemas/agent-event.v0.2.schema.json",
                '  "type": "object",',
                '    "type":     "object",',
            ),
        ),
        (
            # And the case that catches it being rewritten to compare parsed
            # JSON: same keys, same values, different order on the wire.
            "a vendored copy differs only in key order",
            lambda r: edit(
                r,
                "genaryx/crates/core/src/schemas/agent-event.v0.1.schema.json",
                '  "type": "object",\n  "required"',
                '  "required"',
            ),
        ),
    ],
    # ---- C3
    "c3.tokenfuse-unreadable": [(
        "both the artifact and the Rust it falls back to are gone",
        lambda r: (
            drop(r, "tokenfuse/contracts/tokenfuse-constants.json"),
            drop(r, "tokenfuse/crates/core/src/breaker.rs"),
        ),
    )],
    "c3.verdryx-blocked-unreadable": [(
        "the mirror constant is renamed",
        lambda r: edit(r, "verdryx/verdryx/costper.py", "_BLOCKED_DECISIONS = frozenset", "_BLOCKED = frozenset"),
    )],
    "c3.blocked-differ": [
        (
            # tokenfuse has one verdryx does not: verdryx counts an avoided
            # estimate as real spend.
            "the mirror loses one wire string",
            lambda r: edit(r, "verdryx/verdryx/costper.py", '        "dlp_blocked",\n', ""),
        ),
        (
            # And the other direction, which costs the opposite error: verdryx
            # excludes rows tokenfuse no longer blocks.
            "the mirror gains a wire string tokenfuse does not have",
            lambda r: edit(
                r, "verdryx/verdryx/costper.py", '        "dlp_blocked",',
                '        "dlp_blocked",\n        "loop_detected",'
            ),
        ),
    ],
    "c3.verdryx-prices-unreadable": [(
        "the price builder is renamed",
        lambda r: edit(r, "verdryx/verdryx/pricing.py", ".with_price(", ".with_p(", every=True),
    )],
    "c3.prices-differ": [
        (
            "one model's input price differs",
            lambda r: edit(
                r, "verdryx/verdryx/pricing.py",
                "ModelPrice(2.50, 10.00", "ModelPrice(3.50, 10.00"
            ),
        ),
        (
            "a model tokenfuse prices is missing from the mirror",
            lambda r: edit(
                r, "verdryx/verdryx/pricing.py",
                '.with_price("gpt-4o", ModelPrice(2.50, 10.00, 1.25, 2.50))\n            ',
                "",
            ),
        ),
        (
            "the mirror prices a model tokenfuse does not",
            lambda r: edit(
                r, "verdryx/verdryx/pricing.py",
                '.with_price("gpt-4o"',
                '.with_price("o1", ModelPrice(15.0, 60.0, 7.5, 15.0))\n            .with_price("gpt-4o"',
            ),
        ),
    ],
    "c3.verdryx-fallback-missing": [(
        "the mirror has no fallback price",
        lambda r: edit(
            r,
            "verdryx/verdryx/pricing.py",
            ".with_fallback(ModelPrice(15.0, 75.0, 1.5, 18.75))",
            "",
        ),
    )],
    "c3.fallback-differs": [(
        "the fallback price differs",
        lambda r: edit(r, "verdryx/verdryx/pricing.py", "ModelPrice(15.0, 75.0", "ModelPrice(16.0, 75.0"),
    )],
    "c3.verdryx-columns-unreadable": [(
        "the column constants are renamed",
        lambda r: edit(r, "verdryx/verdryx/costper.py", "_PARQUET_", "_PQ_", every=True),
    )],
    "c3.column-absent": [(
        "the mirror reads a column tokenfuse does not write",
        lambda r: edit(
            r, "verdryx/verdryx/costper.py", '_PARQUET_OUTCOME_COLUMN = "outcome"',
            '_PARQUET_OUTCOME_COLUMN = "outcome_tag"'
        ),
    )],
    # ---- C4
    "c4.registry-unparsed": [(
        "SPEC.md loses its 6.2 heading",
        lambda r: edit(r, "agent-passport/SPEC.md", "### 6.2 Initial", "### 6.9 Initial"),
    )],
    "c4.writer-file-gone": [(
        "a producer's writer file is deleted",
        lambda r: drop(r, "qryx/internal/exporter/exporter.go"),
    )],
    "c4.writer-anchor-gone": [(
        "the writer call is renamed, so nothing proves the path exists",
        lambda r: edit(
            r, "mockryx/internal/events/events.go",
            "event.NewChainedWriter(path)", "event.OpenWriter(path)"
        ),
    )],
    "c4.producer-unreadable": [(
        "a producer's emit sites stop parsing",
        lambda r: edit(
            r, "wardryx/internal/api/api.go", "s.emit(", "s.dispatch(", every=True
        ),
    )],
    "c4.reserved-unverifiable": [
        # The RESERVED claim is checked by looking for a Go writer call, so any
        # scan that could not cover the repository must be a red rather than
        # the row holding. Two ways to not cover it, and they are different
        # code paths.
        (
            "a Go file the repo lists cannot be read, so the scan is partial",
            lambda r: drop(r, "idryx/internal/ingest/tokenfuse/tokenfuse.go"),
        ),
        (
            "the RESERVED source's repo has no Go files to look in at all",
            lambda r: git(
                r / "idryx", "rm", "-q", "internal/ingest/tokenfuse/tokenfuse.go"
            ),
        ),
    ],
    "c4.reserved-source-emits": [(
        "the RESERVED source grows an event writer",
        lambda r: edit(
            r,
            "idryx/internal/ingest/tokenfuse/tokenfuse.go",
            "return event.ReadFile(path)",
            "event.NewChainedWriter(path)\n\treturn event.ReadFile(path)",
        ),
    )],
    "c4.registered-source-silent": [(
        "a registered producer's code is gone entirely",
        lambda r: drop(r, "mockryx/internal/events/events.go"),
    )],
    "c4.registered-type-not-emitted": [(
        "a registered type has no emit site",
        lambda r: edit(
            r, "tokenfuse/crates/core/src/agent_event.rs",
            'EventType::RunKilled => "run_killed",', ""
        ),
    )],
    "c4.unregistered-source": [(
        "a producer emits under a source 6.2 does not carry",
        lambda r: edit(
            r, "genaryx/crates/core/src/command.rs",
            'Value::String("console".to_string())', 'Value::String("gonsole".to_string())'
        ),
    )],
    "c4.unregistered-type": [(
        "a producer emits a type 6.2 does not list",
        lambda r: edit(
            r, "mockryx/internal/events/events.go", 'Type: "sim_run",',
            'Type: "sim_run",\n\t})\n}\n\nfunc (e *Emitter) SimFinding() error {\n'
            '\treturn e.write(event.Event{\n\t\tType: "sim_finding",'
        ),
    )],
    # ---- C5
    "c5.expectations-gone": [(
        "the expectations file is not there",
        lambda r: None,  # handled specially: the path is redirected
    )],
    "c5.deployment-unreadable": [(
        "a deployment's anchor file is deleted",
        lambda r: drop(r, "stack-up/routines.sh"),
    )],
    "c5.too-few-deployments": [(
        "only one deployment can be read",
        lambda r: (drop(r, "stack-up/routines.sh"), drop(r, "stack-single/compose.yaml")),
    )],
    "c5.routine-unmapped": [(
        "a deployment installs a routine with an unknown name",
        lambda r: edit(
            r, "stack-up/routines.sh", "mockryx-drill)", "mockryx-drill weekly-sweep)"
        ),
    )],
    "c5.unread-scheduler": [(
        "the deployment that schedules nothing mentions a scheduler",
        lambda r: (r / "stack-single" / "install.sh").write_text(
            (r / "stack-single" / "install.sh").read_text() + "\ncrontab -l\n"
        ),
    )],
    "c5.service-unmapped": [(
        "a deployment brings up a component with an unknown name",
        lambda r: edit(
            r, "stack-single/compose.yaml", "  caddy:\n", "  caddy:\n\n  newthing:\n"
        ),
    )],
    "c5.unrecorded-divergence": [
        # One per fact family, because each family computes its divergence keys
        # with its own code. A single case would prove the reporting works and
        # leave three of the four computations unexercised.
        (
            "a deployment's severity floor changes and nothing records it",
            lambda r: edit(
                r, "stack-k8s/manifests/45-heraldyx.yaml",
                'value: "high"', 'value: "critical"'
            ),
        ),
        (
            "a deployment drops a governance routine and nothing records it",
            lambda r: edit(
                r, "stack-k8s/manifests/40-routines.yaml", "  name: crypto-trend", "  name: drills"
            ),
        ),
        (
            "a deployment moves a component to another port",
            lambda r: edit(
                r, "stack-k8s/manifests/10-planes.yaml",
                "port: 8081, targetPort: http", "port: 8181, targetPort: http"
            ),
        ),
        (
            "a deployment stops bringing up a component",
            lambda r: edit(
                r, "stack-single/compose.yaml",
                "  heraldyx:\n    image: stack/heraldyx:dev\n", ""
            ),
        ),
    ],
    "c5.stale-expectation": [(
        "a recorded divergence stops being one",
        lambda r: edit(r, "stack-single/compose.yaml", "  wg:\n    image: stack/wg:dev\n", ""),
    )],
    # ---- C6
    "c6.canonical-gone": [(
        "the pinned vector file is deleted",
        lambda r: drop(r, "agent-stack-go/event/testdata/chain-vectors.json"),
    )],
    "c6.copy-file-gone": [(
        "a language's copy of the vectors is deleted",
        lambda r: drop(r, "engram/tests/test_events.py"),
    )],
    "c6.copy-unparsed": [(
        "the vector constants are renamed",
        lambda r: edit(r, "verdryx/tests/test_events.py", "_VEC_", "_V_", every=True),
    )],
    "c6.vector-count-differs": [(
        "a copy pins one vector fewer than the file",
        lambda r: edit(
            r, "verdryx/tests/test_events.py",
            f'_VEC_CANONICAL_2 = (\n    {fixture.VEC2_CANON!r}\n)\n'
            f'_VEC_HASH_2 = "{fixture.VEC2_HASH}"\n',
            "",
        ),
    )],
    "c6.canonical-differs": [
        (
            "a copy's canonical string differs by one ASCII byte",
            lambda r: edit(
                r, "engram/tests/test_events.py",
                '"type":"policy_deny"', '"type":"policy_denied"'
            ),
        ),
        (
            # The vector carries non-ASCII text precisely so an encoding
            # difference between Go, Rust and Python cannot hide. A comparison
            # that normalised unicode would pass the ASCII case above.
            "a copy's canonical string differs in its non-ASCII bytes",
            lambda r: edit(
                r, "verdryx/tests/test_events.py", "обмеження", "обмеженнЯ"
            ),
        ),
    ],
    "c6.hash-differs": [(
        "a copy's chain hash differs by one byte",
        lambda r: edit(
            r, "engram/tests/test_events.py",
            fixture.VEC1_HASH, fixture.VEC1_HASH[:-1] + "0"
        ),
    )],
}


# ----------------------------------------------------- reading the gates' AST


def declared_red_paths() -> dict[str, str]:
    """Every finding ID a gate can print FAIL with, read from its source.

    Anchored on the calls, not on a list somebody maintains: a list would be
    another mirror with the same failure mode as the ones this repository was
    built to catch.
    """
    out: dict[str, str] = {}
    for name in GATE_FILES:
        path = HERE / "gates" / name
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not node.args:
                continue
            attr = getattr(node.func, "attr", "")
            if attr not in ("drift", "missing"):
                continue
            first = node.args[0]
            ident = None
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                ident = first.value
            elif isinstance(first, ast.JoinedStr) and first.values:
                head = first.values[0]
                if isinstance(head, ast.Constant) and isinstance(head.value, str):
                    ident = head.value.rstrip(":")
            if ident:
                out[ident] = name
    return out


# --------------------------------------------------------------------- main


def main() -> int:
    problems: list[str] = []

    # -- 3. every red path has a mutation, and no mutation is stale ---------
    declared = declared_red_paths()
    if not declared:
        print("FAIL: no finding IDs could be read out of the gates, so this")
        print("      script measured nothing at all.")
        return 1

    for ident, gate in sorted(declared.items()):
        if ident not in MUTATIONS:
            problems.append(
                f"{gate} can print FAIL with '{ident}' and nothing here makes it "
                f"do so. Add a mutation to MUTATIONS. Until then that line is a "
                f"label, not a check."
            )
    for ident in sorted(MUTATIONS):
        if ident not in declared:
            problems.append(
                f"MUTATIONS has an entry for '{ident}' and no gate prints that "
                f"finding any more. Remove it: a mutation nothing exercises is "
                f"the same decoration one level down."
            )

    work = pathlib.Path(tempfile.mkdtemp(prefix="estate-gates-selftest-"))
    try:
        base = work / "baseline"
        base.mkdir()
        build_estate(base)

        registry = work / "estate.json"
        registry.write_text(json.dumps(fixture.REGISTRY, indent=2), encoding="utf-8")
        expectations = work / "expectations.json"
        expectations.write_text(json.dumps(fixture.EXPECTATIONS, indent=2), encoding="utf-8")

        # -- 1. the baseline is green --------------------------------------
        seen, verdicts, text = run_checks(base, registry, expectations)
        reds = sorted(k for k, v in seen.items() if v == E.DRIFT)
        if reds:
            problems.append(
                f"the fixture estate does not pass today, so it cannot be the "
                f"baseline. Red: {reds}. Either a gate changed or "
                f"selftest/fixture.py did; fix the fixture rather than the gate."
            )
            print(text)
        else:
            print(f"OK: the fixture estate passes all six checks ({', '.join(verdicts)}).")

        # -- 2. each red path fires ----------------------------------------
        if not problems:
            n = 0
            for ident, cases in sorted(MUTATIONS.items()):
                for label, mutate in cases:
                    n += 1
                    case = fresh_copy(base, work, n)
                    exp = expectations
                    if ident == "c5.expectations-gone":
                        exp = work / "no-such-expectations.json"
                    elif mutate is not None:
                        try:
                            mutate(case)
                        except AssertionError as e:
                            problems.append(str(e))
                            continue
                    got, _, out = run_checks(case, registry, exp)
                    if not fired(got, ident):
                        problems.append(
                            f"'{ident}' stayed silent with {label}. It cannot see "
                            f"that failure, which makes it a label for that case "
                            f"rather than a check of it."
                        )

        # -- 4. an unreadable repository is not a pass ----------------------
        unavailable_case = work / "unavailable"
        if not problems:
            case = unavailable_case
            shutil.copytree(base, case)
            shutil.rmtree(case / "taipan")
            got, verdicts, out = run_checks(case, registry, expectations)
            if "C4=" + E.UNAVAILABLE not in verdicts:
                problems.append(
                    f"with taipan removed, C4 reported {verdicts} instead of "
                    f"partial. A repository nothing could read must never come "
                    f"back as agreement."
                )
            if "NOT MEASURED" not in out:
                problems.append(
                    "with taipan removed, no check said out loud that something "
                    "went unmeasured."
                )

        # -- 5. the runner's four exit codes each happen --------------------
        #
        # The exit code is what CI reads, and until this was written it was the
        # one claim in the repository with nothing behind it: exit 3 in
        # particular had never once been produced by a real run, because every
        # real run so far also found drift. A documented exit code no run has
        # ever returned is a comment.
        if not problems:
            for label, expect, root, only in [
                ("a clean, complete estate", 0, base, None),
                ("an estate that drifted", 1, None, None),
                ("a repository that should have been reachable", 2, work / "nowhere", None),
                ("only a repo with no public remote unread", 3, unavailable_case, "c4"),
            ]:
                if root is None:  # the drift case needs a broken estate
                    root = fresh_copy(base, work, 900)
                    edit(
                        root,
                        "genaryx/crates/core/src/schemas/agent-event.v0.2.schema.json",
                        '"prev_hash"',
                        '"previous_hash"',
                    )
                got = run_runner(root, registry, expectations, only)
                if got != expect:
                    problems.append(
                        f"run-gates.py returned {got} for {label}, and README and "
                        f"the workflow both say {expect}. CI reads the exit code "
                        f"and nothing else."
                    )
    finally:
        shutil.rmtree(work, ignore_errors=True)

    if problems:
        print()
        for p in problems:
            print(f"FAIL: {p}")
        print()
        print("A check that cannot fail is worse than no check, because it reports")
        print("green forever. See CLAUDE.md invariant 1.")
        return 1

    cases = sum(len(v) for v in MUTATIONS.values())
    print(
        f"OK: {cases} separate broken estates each turn their own finding red, "
        f"covering"
    )
    print(
        f"    all {len(declared)} FAIL paths across the six gates, and a repository "
        f"nobody could"
    )
    print("    read comes back partial rather than clean.")
    print("    All four of run-gates.py's exit codes were produced by a real run.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
