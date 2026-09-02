#!/usr/bin/env python3
"""C17: a workflow that runs only on a `v*` tag is exercised by a pull request
before it is ever exercised by a tag.

WHY

A workflow gated on `on: push: tags: v*` runs for the first time, on every
commit that ever reaches it, the day somebody cuts a release. Nothing about
that commit is special: the step that fails is whatever nobody happened to run
before. tokenfuse's `binaries` job failed on both Linux runners the first time
`v0.4.2` ever exercised its musl leg, on a step copied from `ci.yml` that lost
the one line pinning the apt snapshot on the way. `git blame` on that step
found nothing recent: it had been wrong since the workflow was written and
every commit since had simply never run it.

The fix, TAIPANBOX/tokenfuse#251, is not "test more". It is two things done
together, because either alone recreates the failure it fixes: the workflow
also runs its BUILD jobs on a pull request that touches the workflow file
itself, so the file is exercised on every edit rather than on the one occasion
that is public; and every job that PUBLISHES is guarded off on that event, so
the same pull request that now runs `binaries` does not also push an image or
cut a release page. Add the first without the second and a pull request
publishes. Add the second without the first and the workflow is exactly as
untested as before.

A survey of every repository in `estate.json` on 2026-09-02 found ten more
workflows with a tag trigger and no pull_request trigger at all: idryx, qryx,
agent-stack-go, costcrew, heraldyx, mockryx, scopyx, wardryx and stack-k8s's
two image workflows. This gate's own discovery, run against the same estate,
also names engram and terraform-provider-taipan, which that survey did not:
both publish (to PyPI and to the Terraform Registry) on a bare `push: tags:
v*` with no escape hatch at all. That is the shape this repository exists to
correct: a hand-typed list is complete on the day it is written, and a
discovered one is not.

WHO THIS DOES NOT ACCUSE

Neither `binaries` above nor an equivalent build-only job is a subject of this
check by itself: a job with no publishing step needs no guard, and this gate
never asks for one. The failure this check is built for is a workflow with NO
escape hatch at all, so its build jobs are never run by anything but the
release, and separately, a publishing job with no guard, so the day a pull
request trigger DOES arrive it publishes from a fork's pull request rather
than only building.

HOW SUBJECTS ARE FOUND

Every repository `estate.json` names, every file under `.github/workflows/`
in it, read at `origin/main` the way every other gate here reads a sibling.
A file is a subject when its `on.push.tags` list holds a pattern starting
with `v` and containing `*`, which is every shape this estate uses today
(`v*` itself, quoted or not, flow-list or block-list). Nothing here is
hand-listed: the ten-versus-twelve gap above is the reason.

HOW IT READS YAML WITHOUT A YAML LIBRARY

This repository is dependency-free by conviction (CLAUDE.md invariant 8), so
this reads the same way C16 reads `compose.yaml`: block boundaries by
indentation, never a real parser. `_indented_block` returns the text under a
`key:` line up to the next line at the same or shallower indentation, which is
enough to find `on:`, then `push:` or `pull_request:` inside it, then `tags:`
or `paths:` inside THAT, and separately `jobs:` at the top and one block per
job inside it. A scalar list is read in both YAML shapes this estate uses:
flow (`tags: ["v*"]`) and block (`tags:\n  - "v*"`).

THE TWO THINGS EVERY SUBJECT MUST HOLD

1. `on.pull_request.paths` names this file's own path, so an edit to the
   workflow is what triggers the build that proves it still works. A bare
   `pull_request:` with no `paths` filter also satisfies this: it runs on
   every pull request, which is a superset of "runs on this file's own
   changes". Neither trailryx nor tokenfuse actually relies on that: both
   scope `paths` to the workflow file (and trailryx also to `Dockerfile`),
   which is the narrower and cheaper thing to do, but a wider net still means
   the file cannot go untested, so this gate accepts it too. `paths-ignore`
   is not read; a file that excludes itself through it would pass here, and
   that is a known gap, stated rather than silently missed.

2. Every job that PUBLISHES carries a job-level `if:` (not a step-level one,
   which this gate is careful to tell apart by indentation) containing one of
   four equivalent expressions, because the estate's real files use more than
   one and all four say the same thing to the scheduler:

     - `github.event_name != 'pull_request'`   (tokenfuse's `build`/`merge`)
     - `startsWith(github.ref, 'refs/tags/')`  (trailryx's, and tokenfuse's
                                                 own `publish` job)
     - `github.event_name == 'push'`
     - `github.ref_type == 'tag'`

   Accepted because each is false on every pull request event regardless of
   what else is true, which is the one property this check needs from a
   guard. A job whose `if:` mentions none of them, or has no `if:` at all,
   fails this even if a human reading the workflow would agree it happens to
   be safe: this check reads the guard's TEXT, the same limit C11 states
   about `chain_proven`, not the scheduler's actual decision.

WHAT COUNTS AS PUBLISHING

A step "publishes" when it: uses `docker/build-push-action` AND that step
also sets `push: true`, `push-by-digest: true`, or embeds `push=true` or
`push-by-digest=true` in a buildx `outputs:` string (tokenfuse's `build` job
does the third; trailryx's `image` job does the first); or uses
`softprops/action-gh-release` or `actions/upload-release-asset`; or its text
contains `docker buildx imagetools create`, `docker push`, `gh release`,
`cosign`, `crane`, or `oras` as a word. A job with at least one such step and
no accepted guard is unguarded. This list is the one named in the task that
produced this gate and nothing wider: engram's `pypi-publish` job and
terraform-provider-taipan's `goreleaser` job both plainly publish and neither
is named here, so this check has no opinion on job guards for those two
files. It still refuses both files under requirement 1 above, because that
requirement does not depend on what a job does.

WHAT IT DOES NOT CATCH

A publish marker spelled a way this gate's text patterns do not recognise: a
custom script wrapping `docker push` in a function, a registry client this
list does not name, a guard expression that is logically equivalent to the
four accepted ones but written differently (`!contains(github.event_name,
'pull_request')`, say). All of those are invisible here, and reporting
agreement about the ones this gate CAN read would be the silence every other
gate in this repository is written to end, so the honest answer is that this
narrows the search rather than closes it. And a workflow whose tag trigger is
written in a form these patterns do not parse (a YAML anchor, the `on: [push]`
shorthand) is invisible the same way a producer's runtime-built event type is
invisible to C4: unmeasured, not passed.
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import _estate as E  # noqa: E402

_WORKFLOW_PATH = re.compile(r"^\.github/workflows/[^/]+\.ya?ml$")


# ------------------------------------------------------- reading YAML as text


def _indented_block(text: str, header: str) -> str | None:
    """Text under a `<indent>header:` line, up to the next sibling at the same
    or a shallower indentation. `None` if the header is not there at all.

    Comment and blank lines never end a block: a `#` line indented less than
    the header is prose, not a sibling key, and stopping on it would truncate
    a block the moment somebody explains it.
    """
    m = re.search(rf"^([ \t]*){re.escape(header)}:[ \t]*$", text, re.M)
    if not m:
        return None
    indent = len(m.group(1))
    start = m.end()
    pos = start
    for line in text[start:].splitlines(keepends=True):
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            this_indent = len(line) - len(line.lstrip(" "))
            if this_indent <= indent:
                break
        pos += len(line)
    return text[start:pos]


def _scalar_list(block: str, key: str) -> list[str] | None:
    """Values of `key:` in `block`, flow style or block style. `None` if the
    key is not there; an empty list is a real, distinct answer (the key is
    there and empty)."""
    sub = _indented_block(block, key)
    if sub is not None:
        items = re.findall(r"^\s*-\s*(.+?)\s*$", sub, re.M)
        return [i.strip(" '\"") for i in items]
    m = re.search(rf"^[ \t]*{re.escape(key)}:\s*\[(.*?)\]", block, re.M)
    if m:
        return [i.strip(" '\"") for i in m.group(1).split(",") if i.strip()]
    return None


_V_STAR = re.compile(r"^v.*\*")


def tag_patterns(text: str) -> list[str]:
    """`on.push.tags`, whatever shape it is written in. Empty if absent."""
    on_block = _indented_block(text, "on")
    if on_block is None:
        return []
    push_block = _indented_block(on_block, "push")
    if push_block is None:
        return []
    return _scalar_list(push_block, "tags") or []


def runs_only_on_a_v_star_tag(text: str) -> bool:
    return any(_V_STAR.match(t) for t in tag_patterns(text))


def pull_request_trigger(text: str) -> tuple[bool, list[str] | None]:
    """(present, paths). `paths` is `None` when the trigger has no `paths`
    filter at all, which this gate reads as "runs on every pull request"."""
    on_block = _indented_block(text, "on")
    if on_block is None:
        return False, None
    pr_block = _indented_block(on_block, "pull_request")
    if pr_block is None:
        return False, None
    return True, _scalar_list(pr_block, "paths")


_JOB_START = re.compile(r"^  ([A-Za-z_][A-Za-z0-9_.-]*):[ \t]*$", re.M)


def jobs_of(text: str) -> dict[str, str]:
    """job id -> its raw body text, read from the top-level `jobs:` block."""
    jobs_block = _indented_block(text, "jobs")
    if not jobs_block:
        return {}
    out: dict[str, str] = {}
    starts = list(_JOB_START.finditer(jobs_block))
    for i, m in enumerate(starts):
        end = starts[i + 1].start() if i + 1 < len(starts) else len(jobs_block)
        out[m.group(1)] = jobs_block[m.end():end]
    return out


_STEP_MARK = re.compile(r"^([ \t]*)-[ \t]", re.M)


def steps_of(steps_block: str) -> list[str]:
    """Each `- ` list item's full text, from its own marker to the next
    sibling marker at the same or a shallower indentation. Used only on a
    job's own `steps:` block, so a `strategy.matrix` list nested deeper never
    reaches this."""
    marks = [(m.start(), len(m.group(1))) for m in _STEP_MARK.finditer(steps_block)]
    out = []
    for i, (pos, indent) in enumerate(marks):
        end = len(steps_block)
        for pos2, indent2 in marks[i + 1:]:
            if indent2 <= indent:
                end = pos2
                break
        out.append(steps_block[pos:end])
    return out


# -------------------------------------------------------- what "publishes" is

_USES_BUILD_PUSH = re.compile(r"uses:\s*docker/build-push-action(?:@|\s|$)")
_USES_GH_RELEASE = re.compile(r"uses:\s*softprops/action-gh-release(?:@|\s|$)")
_USES_UPLOAD_ASSET = re.compile(r"uses:\s*actions/upload-release-asset(?:@|\s|$)")
_PUSH_TRUE = re.compile(r"\bpush:\s*true\b")
_PUSH_BY_DIGEST_TRUE = re.compile(r"\bpush-by-digest:\s*true\b")
_OUTPUTS_PUSH = re.compile(r"outputs:.*\bpush(?:-by-digest)?=true\b")
_SHELL_PUBLISH = re.compile(
    r"\bdocker\s+buildx\s+imagetools\s+create\b"
    r"|\bdocker\s+push\b"
    r"|\bgh\s+release\b"
    r"|\bcosign\b"
    r"|\bcrane\b"
    r"|\boras\b"
)


def step_publish_reason(step_text: str) -> str | None:
    """`None`, or the marker that makes this one step a publish step."""
    if _USES_BUILD_PUSH.search(step_text) and (
        _PUSH_TRUE.search(step_text)
        or _PUSH_BY_DIGEST_TRUE.search(step_text)
        or _OUTPUTS_PUSH.search(step_text)
    ):
        return "docker/build-push-action with push (or push-by-digest) true"
    if _USES_GH_RELEASE.search(step_text):
        return "softprops/action-gh-release"
    if _USES_UPLOAD_ASSET.search(step_text):
        return "actions/upload-release-asset"
    m = _SHELL_PUBLISH.search(step_text)
    return m.group(0) if m else None


def job_level_guard(job_body: str) -> str | None:
    """The job's OWN `if:` expression, never a step's.

    Found by indentation: a job's direct keys (`name`, `needs`, `runs-on`,
    `if`, `steps`, ...) all sit at the indentation of the first real line in
    its body, and a step's `if:` sits deeper, under `steps:`. Matching the
    exact column is what tells them apart, which matters here specifically:
    every real workflow this gate reads also has at least one STEP-level
    `if:` (tokenfuse's musl-only build step, trailryx's architecture-gated
    smoke test), and reading either of those as the job's guard would report
    a publish job as guarded when nothing stops it running on a pull request.
    """
    baseline = None
    for line in job_body.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        baseline = len(line) - len(line.lstrip(" "))
        break
    if baseline is None:
        return None
    m = re.search(rf"^[ \t]{{{baseline}}}if:\s*(.+?)\s*$", job_body, re.M)
    return m.group(1) if m else None


#: Four expressions, because the estate's own clean files use more than one
#: of them and all four are false on every pull_request event. Documented in
#: the module docstring alongside why each is accepted.
_ACCEPTED_GUARD = re.compile(
    r"github\.event_name\s*!=\s*['\"]pull_request['\"]"
    r"|github\.event_name\s*==\s*['\"]push['\"]"
    r"|startsWith\(\s*github\.ref\s*,\s*['\"]refs/tags/"
    r"|github\.ref_type\s*==\s*['\"]tag['\"]"
)


def unguarded_publishers(text: str) -> list[tuple[str, str, str | None]]:
    """[(job id, what makes it a publisher, its `if:` or None)] for every job
    in `text` that publishes and carries no accepted guard."""
    out = []
    for job_id, body in jobs_of(text).items():
        steps_block = _indented_block(body, "steps")
        if not steps_block:
            continue
        reason = None
        for step in steps_of(steps_block):
            reason = step_publish_reason(step)
            if reason:
                break
        if not reason:
            continue
        guard = job_level_guard(body)
        if not guard or not _ACCEPTED_GUARD.search(guard):
            out.append((job_id, reason, guard))
    return out


# --------------------------------------------------------------- the subjects


def tag_triggered_workflows(
    estate: E.Estate, c: E.Check
) -> tuple[list[tuple[str, str, str]], int]:
    """([(repo, path, text)], repos actually searched) for every workflow
    whose `on.push.tags` matches `v*`, discovered across every repository
    `estate.json` names.

    The count is what tells "nothing found because nothing publishes on a
    tag any more" apart from "nothing found because nothing could be read".
    Rule 3 in CLAUDE.md is explicit that the second must never be reported as
    the estate's own agreement: `c.unavailable` above already names every
    repo this run could not reach, so `run` must not ALSO call `c.missing`
    when the reason nothing was found is that none of them could be searched.

    `E.Missing` from `list_files` (git itself failing on an otherwise-valid
    checkout) is treated the way C6's copy search treats it: silently skipped
    rather than reported, because it is not a claim about the ESTATE, and
    every repository this suite reads is a real git checkout where it is not
    expected to happen at all.
    """
    out: list[tuple[str, str, str]] = []
    searched = 0
    for repo in sorted(estate.repos):
        try:
            files = estate.list_files(repo)
        except E.Unavailable as u:
            c.unavailable(
                f"c17.repo-unavailable:{repo}",
                f"{repo} could not be read in this run ({u.reason}), so its "
                f"workflows were not searched.",
            )
            continue
        except E.Missing:
            continue
        searched += 1
        for path in files:
            if not _WORKFLOW_PATH.match(path):
                continue
            try:
                text = estate.read_text(repo, path)
            except E.Missing:
                continue
            if runs_only_on_a_v_star_tag(text):
                out.append((repo, path, text))
    return out, searched


def run(estate: E.Estate) -> E.Check:
    c = E.Check(
        "C17", "a tag-only workflow is exercised by a pull request first", estate
    )

    subjects, searched = tag_triggered_workflows(estate, c)
    if not subjects:
        if searched == 0:
            # Every repository was unavailable, which the c.unavailable calls
            # above already said. Calling c.missing here too would turn "this
            # run could not look" into "the estate has none", which is rule 3:
            # a repository nobody could read is never reported as agreement,
            # and it must not be reported as a FINDING about the estate
            # either.
            return c
        c.missing(
            "c17.no-subjects",
            "no workflow file in any repository estate.json names carries a "
            "`push.tags` trigger matching `v*`, so this gate measured "
            "nothing. Either every such workflow was removed, or the trigger "
            "is written in a form this gate's text reader does not "
            "recognise, and both need a person rather than a green run.",
        )
        return c

    c.note(
        f"{len(subjects)} workflow(s) run only on a `v*` tag, across "
        f"{len({r for r, _, _ in subjects})} repositor(y/ies)."
    )

    for repo, path, text in sorted(subjects):
        has_pr, paths = pull_request_trigger(text)
        covers_self = has_pr and (paths is None or path in paths)
        bad_jobs = unguarded_publishers(text)

        if not covers_self:
            if not has_pr:
                trigger_has = "no `pull_request` trigger at all"
            else:
                trigger_has = f"a `pull_request` trigger whose `paths` is {paths} and does not name this file"
            c.drift(
                f"c17.no-pull-request-for-self:{repo}/{path}",
                f"{repo}/{path} runs only on a `v*` tag and has {trigger_has}.",
                [
                    f"  file:             {estate.where(repo, path)}",
                    f"  trigger it has:   on.push.tags = {tag_patterns(text)!r}; {trigger_has}",
                    f"  trigger it needs: on.pull_request.paths including \"{path}\"",
                    "  A workflow that runs only on a tag is first exercised by the",
                    "  release itself. TAIPANBOX/tokenfuse#251 is the shape of the fix:",
                    "  add a pull_request trigger scoped to this file's own path.",
                ],
            )

        if bad_jobs:
            detail = [f"  file: {estate.where(repo, path)}"]
            for job_id, reason, guard in bad_jobs:
                detail.append(
                    f"  job `{job_id}` publishes ({reason}); if: {guard or '(none)'}"
                )
            detail += [
                "  guard it needs: `if:` containing github.event_name != 'pull_request'",
                "  (or an equivalent: startsWith(github.ref, 'refs/tags/'),",
                "  github.event_name == 'push', github.ref_type == 'tag')",
                "  A pull_request build that reaches this job without the guard",
                "  would publish from a fork's pull request.",
            ]
            c.drift(
                f"c17.publish-job-unguarded:{repo}/{path}",
                f"{repo}/{path} has {len(bad_jobs)} job(s) that publish and "
                f"are not guarded off on a pull request.",
                detail,
            )

        if covers_self and not bad_jobs:
            c.ok(
                f"c17.guarded:{repo}/{path}",
                f"{repo}/{path} builds on a pull request that touches itself "
                f"and every publishing job is guarded off that event.",
            )

    return c


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    E.add_common_args(parser)
    args = parser.parse_args()
    return run(E.estate_from_args(args)).render()


if __name__ == "__main__":
    raise SystemExit(main())
