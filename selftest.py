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
one sitting and wired so every check agrees. This script materialises it as
real git repositories in a temporary directory, proves they all pass, then
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
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "gates"))
sys.path.insert(0, str(HERE / "selftest"))

import _estate as E  # noqa: E402
import fixture  # noqa: E402

def _gate_files() -> list[str]:
    """The gate list, read out of `run-gates.py` rather than kept beside it.

    This file held its own copy until 2026-08-26, and the runner held a literal
    `GATES` list until later the same day. Two lists that must agree, with
    nothing comparing them, is the exact defect shape this suite exists to find
    in other repositories, and the failure it invites is the quiet one: a gate
    in one list and not the other ships UNPROVEN while the summary reports green
    about the gates it knew about.

    So neither place has a list any more. The runner DISCOVERS the gate files in
    `gates/`, and this reads the same directory the same way, which is the only
    arrangement where the two cannot disagree.

    Read by globbing rather than by importing the runner, because its filename
    carries a hyphen and cannot be imported by name. An empty directory raises
    here rather than silently reading as "nothing to prove".
    """
    found = sorted(
        (HERE / "gates").glob("c*.py"),
        key=lambda p: (int(re.match(r"c(\d+)", p.stem).group(1)), p.stem),
    )
    names = [p.name for p in found if re.match(r"c\d+-", p.stem)]
    if not names:
        raise SystemExit(
            "no gate was found in gates/, so this self-test would prove nothing"
        )
    return names


GATE_FILES = _gate_files()


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
    """Run every gate against `root`.

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


def plant(root: pathlib.Path, rel: str, contents: str) -> None:
    """Add a NEW tracked file to a fixture repository.

    `git add` and not just a write, because the checks read what git tracks. An
    untracked file is invisible to them, so planting one and calling it a
    mutation would prove nothing.
    """
    p = root / rel
    if p.exists():
        raise AssertionError(f"selftest mutation is stale: {rel} is already in the fixture")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(contents, encoding="utf-8")
    git(root / rel.split("/", 1)[0], "add", rel.split("/", 1)[1])


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
            # Every consumer, and the list must grow with the fixture: scopyx
            # joined it in G4.4, and until it was added here the mutation left
            # one consumer standing and c1.no-consumers could not fire.
            for repo in ("idryx", "qryx", "wardryx", "mockryx", "heraldyx",
                         "scopyx", "terraform-provider-taipan")
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
    # ---- C7
    # ---- C9
    # ---- C10
    "c10.mapping-disagrees-across-languages": [
        (
            "the Rust side reverses the chain and nothing in Rust notices",
            lambda r: edit(
                r,
                "tokenfuse/crates/delegation/src/lib.rs",
                '"user://acme/alice",\n                "agent://acme/triage",\n                "agent://acme/runbook"',
                '"agent://acme/runbook",\n                "agent://acme/triage",\n                "user://acme/alice"',
            ),
        ),
        (
            # The two actors swapped, which is the direction failure and the
            # one no signature check can catch: three principals, a human at
            # the root, and the wrong agent named as the immediate actor.
            #
            # NOT "the subject is dropped": that leaves two principals and
            # exercises c10.vector-too-short instead, which is a different red
            # path and has its own mutation. The self-test caught that
            # mislabelling.
            "the Go side swaps the two actors, inverting who delegated to whom",
            lambda r: edit(
                r,
                "agent-stack-go/delegation/chain_test.go",
                'want := "user://acme/alice,agent://acme/triage,agent://acme/runbook"',
                'want := "user://acme/alice,agent://acme/runbook,agent://acme/triage"',
            ),
        ),
    ],
    "c10.vector-has-no-human-at-its-root": [(
        "both sides agree on a vector with no person in it, so the worst failure cannot show",
        lambda r: (
            edit(
                r,
                "agent-stack-go/delegation/chain_test.go",
                'want := "user://acme/alice,agent://acme/triage,agent://acme/runbook"',
                'want := "agent://acme/cron,agent://acme/triage,agent://acme/runbook"',
            ),
            edit(
                r,
                "tokenfuse/crates/delegation/src/lib.rs",
                '"user://acme/alice",\n                "agent://acme/triage",',
                '"agent://acme/cron",\n                "agent://acme/triage",',
            ),
        ),
    )],
    "c10.no-assertion-to-read": [(
        "the Go vector stops asserting anything, leaving only the token's own literals",
        lambda r: edit(
            r,
            "agent-stack-go/delegation/chain_test.go",
            'want := "user://acme/alice,agent://acme/triage,agent://acme/runbook"',
            'noAssertionHere := 1',
        ),
    )],
    "c10.no-implementation-to-read": [(
        "the Rust implementation is gone",
        lambda r: drop(r, "tokenfuse/crates/delegation/src/lib.rs"),
    )],
    "c10.no-vector-to-read": [(
        "the Go vector's test is renamed away, so nothing asserts the mapping",
        lambda r: edit(
            r,
            "agent-stack-go/delegation/chain_test.go",
            "func TestTheEstateChainCarriesTheSubjectAndTheRfcsActDoesNot",
            "func TestSomethingElseEntirely",
        ),
    )],
    "c10.vector-too-short": [(
        "the Go vector shrinks below a subject and two actors",
        lambda r: edit(
            r,
            "agent-stack-go/delegation/chain_test.go",
            'want := "user://acme/alice,agent://acme/triage,agent://acme/runbook"',
            'want := "user://acme/alice"',
        ),
    )],
    "c9.foreign-git-keeps-the-environment": [
        (
            "a foreign-target git call stops clearing the hook's variables",
            lambda r: edit(
                r,
                "trailryx/scripts/audit.sh",
                'env -u GIT_DIR -u GIT_WORK_TREE -u GIT_INDEX_FILE git -C "$db"',
                'git -C "$db"',
            ),
        ),
        (
            "it clears something else and leaves GIT_DIR set, which is the one that bites",
            lambda r: edit(
                r,
                "trailryx/scripts/audit.sh",
                "env -u GIT_DIR -u GIT_WORK_TREE -u GIT_INDEX_FILE git",
                "env -u GIT_WORK_TREE -u GIT_INDEX_FILE git",
            ),
        ),
        (
            # The self-exclusion is not blanket: point the same call somewhere
            # else and it must fire. Without this the exclusion could be a
            # wildcard nobody noticed.
            "the call that names this repository is pointed at a sibling",
            lambda r: edit(
                r,
                "trailryx/scripts/audit.sh",
                'git -C "$(git rev-parse --show-toplevel)" status',
                'git -C ../agent-passport status',
            ),
        ),
    ],
    "c9.nothing-scanned": [(
        "every script the check reads is gone",
        lambda r: drop(r, "trailryx/scripts/audit.sh"),
    )],
    # ---- C8
    "c8.type-unanswered": [
        (
            "a registered type loses its mapping arm and nobody names it refused",
            lambda r: edit(
                r,
                "trailryx/crates/trailryx-agentevent/src/lib.rs",
                '        "run_killed" => m(EventType::RunCompleted),\n',
                "",
            ),
        ),
        (
            "a type named as refused drops out of the passage that names it",
            lambda r: edit(
                r,
                "trailryx/crates/trailryx-agentevent/src/lib.rs",
                "`crypto_finding`, `eval_run`,\n//! `sim_run`",
                "`eval_run`,\n//! `sim_run`",
            ),
        ),
        (
            "the registry grows a type the record plane has never heard of",
            lambda r: edit(
                r,
                "agent-passport/SPEC.md",
                "| `wardryx` | `policy_allow` . `policy_deny` |",
                "| `wardryx` | `policy_allow` . `policy_deny` . `policy_updated` |",
            ),
        ),
    ],
    "c8.registry-unparsed": [(
        # The same fault C4 plants, and deliberately so: both gates read one
        # parser now, and a mutation that fires only one of them would leave
        # the other's unparsed path unproven the day the parser changes.
        "SPEC.md loses its 6.2 heading",
        lambda r: edit(r, "agent-passport/SPEC.md", "### 6.2 Initial", "### 6.9 Initial"),
    )],
    "c8.mapper-file-gone": [(
        "the record plane's ingest door is deleted",
        lambda r: drop(r, "trailryx/crates/trailryx-agentevent/src/lib.rs"),
    )],
    "c8.mapper-unreadable": [
        (
            "the mapping function is renamed, so the arms cannot be found",
            lambda r: edit(
                r,
                "trailryx/crates/trailryx-agentevent/src/lib.rs",
                "fn mapping_for",
                "fn record_type_for",
            ),
        ),
        (
            "the fallback arm goes, so the extractor has nowhere to stop",
            lambda r: edit(
                r,
                "trailryx/crates/trailryx-agentevent/src/lib.rs",
                "        _ => None,\n",
                "",
            ),
        ),
        (
            "the passage naming deliberate refusals loses its own anchor",
            lambda r: edit(
                r,
                "trailryx/crates/trailryx-agentevent/src/lib.rs",
                "Refused today",
                "Not mapped at present",
            ),
        ),
    ],
    "c7.canonical-gone": [(
        "agent-passport's v0.2 schema is deleted",
        lambda r: drop(r, "agent-passport/schemas/agent-event.v0.2.schema.json"),
    )],
    "c7.canonical-unusable": [
        (
            "the canonical schema stops stating an agent_id pattern",
            lambda r: edit(
                r,
                "agent-passport/schemas/agent-event.v0.2.schema.json",
                '"pattern": "^agent://[a-z0-9.-]+/[a-z0-9._/-]+$", ',
                "",
            ),
        ),
        (
            "the canonical schema stops stating the cap, which is half the rule",
            lambda r: edit(
                r,
                "agent-passport/schemas/agent-event.v0.2.schema.json",
                ', "maxLength": 255',
                "",
            ),
        ),
    ],
    "c7.copy-gone": [(
        "a repository that carried the rule loses the file it lived in",
        lambda r: drop(r, "engram/engram/events.py"),
    )],
    "c7.anchor-gone": [
        (
            "the python copy's constant is renamed",
            lambda r: edit(r, "verdryx/verdryx/events.py", "AGENT_ID_PATTERN =", "AGENT_URI_RE ="),
        ),
        (
            "the go copy's variable is renamed",
            lambda r: edit(
                r, "agent-stack-go/passport/passport.go", "agentURIPattern =", "uriRe ="
            ),
        ),
    (
            # The rust copy anchors on a FUNCTION rather than a constant, which
            # is a shape none of the other three have. It gets its own case.
            "the rust copy's function is renamed",
            lambda r: edit(
                r,
                "tokenfuse/crates/core/src/agent_event.rs",
                "fn is_canonical_agent_id",
                "fn agent_id_is_canonical",
            ),
        ),
    ],
    "c7.pattern-differs": [
        (
            "a copy loosens the grammar",
            lambda r: edit(
                r,
                "engram/engram/events.py",
                r"^agent://[a-z0-9.-]+/[a-z0-9._/-]+$",
                r"^agent://.+$",
            ),
        ),
        (
            "the go copy in the module six repos import drifts",
            lambda r: edit(
                r,
                "agent-stack-go/passport/passport.go",
                r"^agent://[a-z0-9.-]+/[a-z0-9._/-]+$",
                r"^agent://[A-Za-z0-9.-]+/[a-z0-9._/-]+$",
            ),
        ),
    (
            "the rust copy loosens the grammar",
            lambda r: edit(
                r,
                "tokenfuse/crates/core/src/agent_event.rs",
                r"^agent://[a-z0-9.-]+/[a-z0-9._/-]+$",
                r"^agent://.+$",
            ),
        ),
    ],
    "c7.cap-anchor-gone": [(
        "a copy stops naming a cap at all",
        lambda r: edit(r, "engram/engram/events.py", "AGENT_ID_MAX_LENGTH = 255", ""),
    )],
    "c7.cap-differs": [
        (
            "a python copy caps lower than the envelope",
            lambda r: edit(
                r, "verdryx/verdryx/events.py", "AGENT_ID_MAX_LENGTH = 255", "AGENT_ID_MAX_LENGTH = 128"
            ),
        ),
        (
            "the go copy caps higher than the envelope",
            lambda r: edit(
                r, "agent-stack-go/passport/passport.go", "maxURIBytes = 255", "maxURIBytes = 1024"
            ),
        ),
    (
            "the rust copy caps lower than the envelope",
            lambda r: edit(
                r,
                "tokenfuse/crates/core/src/agent_event.rs",
                "AGENT_ID_MAX_LENGTH: usize = 255",
                "AGENT_ID_MAX_LENGTH: usize = 64",
            ),
        ),
    ],
    # ---- C11
    "c12.member": [
        (
            # The real finding, planted: a spec envelope member the store never
            # heard of. It is not refused and not counted; it lands in the
            # payload plane, which a per-event key erases, and SPEC 5.2 reads a
            # chain with no proof beside it as NOT proven. A routine erasure
            # then downgrades a proven chain to an unproven one, silently.
            "the record plane has no decision about a spec envelope member",
            lambda r: edit(
                r,
                "trailryx/crates/trailryx-agentevent/src/lib.rs",
                '    "delegation_proof",\n',
                "",
            ),
        ),
        (
            # The same hole one step subtler: the member is named in the doc but
            # OUTSIDE the passage that argues the plane boundary. Prose that
            # mentions a member is not prose that decides about it, and an
            # extractor scanning the whole module doc would call this an answer.
            "a member mentioned in the doc but outside the plane-boundary passage",
            lambda r: edit(
                r,
                "trailryx/crates/trailryx-agentevent/src/lib.rs",
                '    "delegation_proof",\n',
                "",
            )
            or edit(
                r,
                "trailryx/crates/trailryx-agentevent/src/lib.rs",
                "//! # Rule two: nothing is invented",
                "//! # Rule two: nothing is invented\n//!\n//! `delegation_proof` is mentioned here and decided nowhere.",
            ),
        ),
    ],
    "c12.mapper-unreadable": [(
        # The anchors this gate reads the mapper through are its subject list.
        # An anchor that stops matching must be a finding, never a skip: a gate
        # that quietly reads an empty list of consumed members would report that
        # every member is in the payload plane and pass.
        "the mapper's own list of typed members is gone",
        lambda r: edit(
            r,
            "trailryx/crates/trailryx-agentevent/src/lib.rs",
            "const CONSUMED: &[&str] = &[",
            "const KEPT_MEMBERS: &[&str] = &[",
        ),
    )],
    "c12.schemas": [(
        # The subjects are DISCOVERED from the schema files. A gate that can no
        # longer find one must say it measured nothing rather than report that
        # every member it knows about has a plane.
        "the envelope schemas it reads its subjects from are gone",
        lambda r: edit(
            r,
            "agent-stack-go/cmd/agent-conform/schemas/agent-event.schema.json",
            '"properties"',
            '"disabled_properties"',
            every=True,
        )
        or edit(
            r,
            "agent-stack-go/cmd/agent-conform/schemas/agent-event.v0.2.schema.json",
            '"properties"',
            '"disabled_properties"',
            every=True,
        )
        or edit(
            r,
            "agent-stack-go/cmd/agent-conform/schemas/agent-event.v0.3.schema.json",
            '"properties"',
            '"disabled_properties"',
            every=True,
        ),
    )],
    "c11.asserted-not-verified": [
        (
            # The rubber stamp: a producer that tells the PDP a chain was proved
            # with no verification anywhere in the file. wardryx believes it, and
            # `deny_if_chain_unproven` then never fires.
            "an enforcement point asserts a proved chain without verifying one",
            lambda r: edit(
                r,
                "tokenfuse/crates/gateway/src/chainproof.rs",
                "match crate::chainproof::resolve(&req.cfg, req.token(), req.proof()) {",
                "match req.declared_chain() {",
            ),
        ),
        (
            # The same thing one layer subtler: the import survives and the call
            # does not, which is what a refactor leaves behind.
            "the verifier is imported, mentioned in a comment, and never called",
            lambda r: edit(
                r,
                "tokenfuse/crates/gateway/src/chainproof.rs",
                "crate::chainproof::resolve(&req.cfg, req.token(), req.proof())",
                "req.declared_chain() /* verify_delegation was here */",
            ),
        ),
    ],
    "c11.no-producer": [(
        # The field is RENAMED, so it exists nowhere. That is the case worth
        # catching: a rename leaves this gate looking for a string that no
        # longer exists, which would make it permanently and quietly green.
        #
        # It used to plant `chain_proven: proved` instead, back when this gate
        # counted literal assertions rather than mentions. That version of the
        # gate reported `measured nothing` about the real estate, whose two
        # doors set the value from a match arm and never write the literal at
        # all. Counting mentions fixed the gate and made that mutation useless,
        # which is the mutation doing its job in reverse.
        "the field the PDP decides on is renamed away",
        lambda r: edit(
            r,
            "tokenfuse/crates/gateway/src/chainproof.rs",
            "chain_proven",
            "chain_was_proved",
            every=True,
        ),
    )],
    "c4.producer-undeclared": [
        (
            # A new service starts writing events and nobody adds it to
            # PRODUCERS, which is what happened to vouchryx: it wrote three
            # types from the day it existed and this gate reported clean on the
            # eight it knew. The repository is arbitrary; what matters is a
            # writer where the declared list has no entry.
            "a service writes events and PRODUCERS has no entry for it",
            lambda r: plant(
                r,
                "catalog/cmd/emitter/main.go",
                'package main\n\nfunc main() {\n\tw, _ := event.NewChainedWriter("e.ndjson")\n\t_ = w\n}\n',
            ),
        ),
        (
            # And the Python spelling, because two of the estate's producers are
            # Python and a search that only knew Go would be half a check.
            "a Python service writes events and PRODUCERS has no entry for it",
            lambda r: plant(
                r,
                "catalog/emitter/events.py",
                'class EventLog:\n    def emit(self, kind):\n        pass\n',
            ),
        ),
    ],
    # ---- C2
    "c2.canonical-gone": [(
        "the canonical schema is deleted",
        lambda r: drop(r, "agent-passport/schemas/agent-event.schema.json"),
    )],
    "c2.copy-gone": [(
        "a vendored copy is deleted",
        lambda r: drop(r, "engram/tests/fixtures/agent-event.v0.2.schema.json"),
    )],
    "c2.copy-unwatched": [
        (
            # The defect exactly as it happened on 2026-08-26: a repository
            # keeps a copy of a canonical schema at a path COPIES never
            # mentioned, so nothing ever compared it and it drifted in silence.
            "a repository vendors a copy nobody declared",
            lambda r: plant(
                r,
                "tokenfuse/crates/core/src/schemas/agent-event.v0.2.schema.json",
                fixture.EVENT_V02,
            ),
        ),
        (
            # And the case that catches discovery being keyed on the filename
            # instead of on what the file CLAIMS. A copy under any name is a
            # copy, and a renamed one is the easiest kind to forget.
            "an undeclared copy is filed under a name no schema uses",
            lambda r: plant(r, "engram/tests/fixtures/envelope.json", fixture.EVENT_V02),
        ),
    ],
    "c2.canonical-has-no-id": [(
        "the canonical schema stops saying what it is",
        lambda r: edit(
            r,
            "agent-passport/schemas/agent-event.v0.2.schema.json",
            '  "$id": "https://taipanbox.dev/agent-passport/v0.2/agent-event.schema.json",\n',
            "",
        ),
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
    "c4.producer-unreadable": [
        (
            "a producer's emit sites stop parsing",
            lambda r: edit(
                r, "wardryx/internal/api/api.go", "s.emit(", "s.dispatch(", every=True
            ),
        ),
        # G4.4. Both of these were CLEAN before the fix: the identifier was
        # dropped, the anchor still matched the file, and the run said "every
        # subject was measured" about a producer whose types it never read.
        (
            "a producer computes its event type instead of naming a constant",
            lambda r: edit(
                r,
                "scopyx/internal/record/record.go",
                "return j.emit(TypeFetch, agentID)",
                "return j.emit(chooseType(), agentID)",
            ),
        ),
        (
            "a producer's type constant is renamed out from under the emit site",
            lambda r: edit(
                r,
                "scopyx/internal/record/record.go",
                '\tTypeBlocked = "web_blocked"',
                '\tTypeRefused = "web_blocked"',
            ),
        ),
    ],
    # THE RESERVED BRANCH NO LONGER HAS A STANDING SUBJECT, SO EACH CASE PLANTS
    # ONE.
    #
    # idryx was the estate's only RESERVED row and stopped being one on
    # 2026-08-10, when it gained a writer and 6.2 was corrected in the same
    # wave. The branch stays, because the next reserved row must not ship with
    # nothing checking it, and the state it guards is the expensive one: a row
    # telling consumers "do not expect these events" while a writer quietly
    # exists.
    #
    # Planting is stronger than the old shape, which relied on the fixture
    # happening to hold a reserved source. These cases now CREATE the exact
    # contradiction and require the gate to name it.
    "c4.reserved-unverifiable": [
        # RESERVED plus a scan that could not cover the repository. Two ways to
        # not cover it, and they are different code paths.
        (
            "a RESERVED row whose repo has a Go file that cannot be read",
            lambda r: [
                edit(
                    r,
                    "agent-passport/SPEC.md",
                    "| `idryx` | `identity_finding` |",
                    "| `idryx` | RESERVED, not emitted today: `identity_finding` |",
                ),
                drop(r, "idryx/internal/ingest/tokenfuse/tokenfuse.go"),
                drop(r, "idryx/internal/events/events.go"),
            ],
        ),
        (
            "a RESERVED row whose repo has no Go files to look in at all",
            lambda r: [
                edit(
                    r,
                    "agent-passport/SPEC.md",
                    "| `idryx` | `identity_finding` |",
                    "| `idryx` | RESERVED, not emitted today: `identity_finding` |",
                ),
                git(r / "idryx", "rm", "-q", "internal/ingest/tokenfuse/tokenfuse.go"),
                git(r / "idryx", "rm", "-q", "internal/events/events.go"),
            ],
        ),
    ],
    "c4.reserved-source-emits": [(
        "a row says RESERVED while the repo has a writer, which is the state "
        "this branch exists for",
        lambda r: edit(
            r,
            "agent-passport/SPEC.md",
            "| `idryx` | `identity_finding` |",
            "| `idryx` | RESERVED, not emitted today: `identity_finding` |",
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

    # A duplicate key in MUTATIONS is silently lost: Python keeps the last one
    # and the dict never says so. That happened while writing the G4.4 cases,
    # which were added under a key that already existed forty lines further
    # down, ran nothing, and left the count unchanged at a number nobody was
    # watching. Read from the source rather than the dict, because by the time
    # it IS a dict the evidence is gone.
    _keys = re.findall(r'^    "([a-z0-9]+\.[a-z-]+)":', pathlib.Path(__file__).read_text(), re.M)
    _dupes = sorted({k for k in _keys if _keys.count(k) > 1})
    if _dupes:
        problems.append(
            f"MUTATIONS declares {_dupes} more than once. Python keeps the last "
            f"one and discards the rest silently, so those cases run nothing "
            f"while reading as added. Merge them into one entry."
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
            print(
                f"OK: the fixture estate passes every check "
                f"({', '.join(verdicts)})."
            )

        # -- 1b. every gate can be RUN, on its own -------------------------
        #
        # `run-gates.py` imports each gate and calls its `run(estate)`, so a
        # gate whose own `main()` is broken runs perfectly through the runner
        # and crashes when a person invokes the file. Measured 2026-08-26: C8,
        # C9 and C10 called `Estate.run_one`, a method that does not exist.
        # All three shipped, all three read as `clean` in every summary, and
        # every single-gate invocation in the README raised AttributeError.
        #
        # A mutation harness cannot see this: it proves what a gate FINDS, and
        # this is about whether the gate can be started at all.
        if not problems:
            for name in GATE_FILES:
                done = subprocess.run(
                    [
                        sys.executable,
                        str(HERE / "gates" / name),
                        "--root",
                        str(base),
                        "--registry",
                        str(registry),
                    ],
                    capture_output=True,
                    text=True,
                    env=dict(os.environ, ESTATE_GATES_EXPECTATIONS=str(expectations)),
                )
                # Exactly clean, because the fixture IS clean and every gate
                # just reported so through the runner. Accepting "any exit code
                # a gate is allowed to produce" would accept 1, and an uncaught
                # Python exception exits 1: the first version of this check
                # passed with C9's crash planted back in, which is how it was
                # found to be measuring nothing.
                if done.returncode != E.EXIT_CLEAN:
                    problems.append(
                        f"{name} does not run cleanly on its own against the "
                        f"fixture every gate just passed: exit "
                        f"{done.returncode}.\n{done.stderr.strip()[-400:]}"
                    )
            if not problems:
                print(
                    f"OK: all {len(GATE_FILES)} gates run standalone, not only "
                    f"through run-gates.py."
                )

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
        f"    all {len(declared)} FAIL paths across {len(GATE_FILES)} gates, and a repository "
        f"nobody could"
    )
    print("    read comes back partial rather than clean.")
    print("    All four of run-gates.py's exit codes were produced by a real run.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
