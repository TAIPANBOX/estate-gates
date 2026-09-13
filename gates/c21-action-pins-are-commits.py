#!/usr/bin/env python3
"""C21: every GitHub Action a workflow uses is pinned to a COMMIT of that
action, not to a tag name and not to the SHA of an annotated tag object.

WHY

On 2026-09-12 twenty-one repositories pinned `ossf/scorecard-action` to
`55891bbd73f2425e97637d96e306fc9d491d0b21 # v2.4.4`. That SHA is real and the
workflow runs: GitHub resolves an annotated tag object when it checks the
action out. It is the SHA of the TAG OBJECT of v2.4.4, not of the commit the
tag points to (`2d1146689b8cda280b9bc96326124645441f03bc`), because
`git rev-parse v2.4.4` and the GitHub API's `git/ref/tags/v2.4.4` both answer
with the tag object for an annotated tag. Every Scorecard run in the estate
then ended with `workflow verification failed: imposter commit: 55891bb...`
from api.scorecard.dev, three retries, one warning nobody read, and no
repository has a published score (SUP-4 of the 1.0 proving run, 2026-09-13).
Dependabot never touched it: the pin looks current.

A pin that is a tag name is the older failure the 2026-09-06 review closed:
`actions/checkout@v4` moves when the tag moves. This gate holds both.

WHAT IS READ

Every `.github/workflows/*.yml` and `*.yaml` of every repository estate.json
names, and in each the `uses: <owner>/<repo>[/<path>]@<ref>` lines. Local
actions (`./...`) carry no `@` and `docker://` images no `owner/repo`, so
neither matches and neither is judged. The reference of each distinct action repository is read once
with `git ls-remote --tags --heads` and classified: a SHA listed as
`refs/tags/<t>` with a different peeled `refs/tags/<t>^{}` is a tag object;
a SHA listed peeled, or as a lightweight tag, or as a branch head, is a
commit. A SHA at no ref tip at all (an older commit, the common case for a
pin two releases behind) cannot be classified from the tips and is reported
as read but not judged, never as a pass.

WHAT COUNTS AS A FAILURE

  c21.unpinned           `@<ref>` is not a 40-hex SHA: a tag or branch that moves
  c21.tag-object         the SHA is an annotated tag OBJECT; the fix is the
                         peeled commit, which the finding names
  c21.remote-unavailable `git ls-remote` of the action repository did not
                         answer, so its pins could not be judged
  c21.no-subjects        no workflow in the estate uses an action, so this
                         gate measured nothing; two dozen do

ESTATE_GATES_ACTION_REFS names a JSON file (`{"owner/repo": {"<sha>":
"tag-object" | "commit"}}`) that stands in for `ls-remote` under the selftest.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import _estate as E  # noqa: E402

_USES = re.compile(r"^\s*-?\s*uses:\s*['\"]?([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)(?:/[^@\s'\"]+)?@([^\s'\"#]+)")
_SHA = re.compile(r"^[0-9a-f]{40}$")


class ActionRefs:
    """What each action repository's ref tips say about a SHA."""

    def __init__(self) -> None:
        fixture = os.environ.get("ESTATE_GATES_ACTION_REFS")
        self.fixture = json.loads(pathlib.Path(fixture).read_text()) if fixture else None
        self.cache: dict[str, dict[str, str] | None] = {}

    def classify(self, action: str) -> dict[str, str] | None:
        """sha -> 'tag-object' | 'commit', or None when the remote did not answer."""
        if action in self.cache:
            return self.cache[action]
        if self.fixture is not None:
            self.cache[action] = dict(self.fixture.get(action, {}))
            return self.cache[action]
        proc = subprocess.run(
            ["git", "ls-remote", "--tags", "--heads", f"https://github.com/{action}"],
            capture_output=True,
            text=True,
            timeout=60,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
        )
        if proc.returncode != 0:
            self.cache[action] = None
            return None
        tags: dict[str, str] = {}
        peeled: dict[str, str] = {}
        kinds: dict[str, str] = {}
        for line in proc.stdout.splitlines():
            sha, _, ref = line.partition("\t")
            if ref.startswith("refs/heads/"):
                kinds[sha] = "commit"
            elif ref.endswith("^{}"):
                peeled[ref[: -len("^{}")]] = sha
            elif ref.startswith("refs/tags/"):
                tags[ref] = sha
        for ref, sha in tags.items():
            if ref in peeled and peeled[ref] != sha:
                kinds[sha] = "tag-object"
                kinds[peeled[ref]] = "commit"
            else:
                kinds[sha] = "commit"
        self.cache[action] = kinds
        return kinds


def run(estate: E.Estate) -> E.Check:
    c = E.Check("C21", "every action a workflow uses is pinned to a commit", estate)
    refs = ActionRefs()
    subjects = 0
    unread = 0
    unjudged = 0
    for repo in sorted(estate.repos):
        try:
            files = [
                f
                for f in estate.list_files(repo)
                if f.startswith(".github/workflows/") and (f.endswith(".yml") or f.endswith(".yaml"))
            ]
        except E.Missing:
            continue
        except E.Unavailable as u:
            c.unavailable(f"c21.workflows-unavailable:{repo}", str(u))
            unread += 1
            continue
        for f in files:
            try:
                text = estate.read_text(repo, f)
            except E.Missing:
                # Tracked and gone from the tree (a deletion not yet committed):
                # nothing to read, and nothing this gate can say about it.
                continue
            except E.Unavailable as u:
                c.unavailable(f"c21.workflow-unavailable:{repo}:{f}", str(u))
                unread += 1
                continue
            for lineno, line in enumerate(text.splitlines(), start=1):
                m = _USES.match(line)
                if not m:
                    continue
                action, ref = m.group(1), m.group(2)
                subjects += 1
                where = f"{estate.where(repo, f)} line {lineno}"
                if not _SHA.match(ref):
                    c.drift(
                        "c21.unpinned",
                        f"{repo} uses {action}@{ref}, a reference that moves; pin the commit SHA and keep the tag as a comment.",
                        [f"  {where}"],
                    )
                    continue
                kinds = refs.classify(action)
                if kinds is None:
                    c.unavailable(f"c21.remote-unavailable:{action}", f"git ls-remote of {action} did not answer, so its pins were not judged")
                    continue
                kind = kinds.get(ref)
                if kind == "tag-object":
                    peel = next((s for s, k in kinds.items() if k == "commit" and s != ref), None)
                    commit = _peeled_commit_for(refs, action, ref)
                    c.drift(
                        "c21.tag-object",
                        f"{repo} pins {action}@{ref[:7]}, which is the SHA of an annotated TAG OBJECT, not a commit: "
                        f"the workflow runs, and anything that verifies the pin against the action's commits refuses it "
                        f"(Scorecard: \"imposter commit\").",
                        [f"  {where}", f"  pin the commit the tag points to instead: {commit or peel or '(read it with git ls-remote --tags, the ^{{}} line)'}"],
                    )
                elif kind == "commit":
                    c.ok(f"c21.commit:{repo}:{action}:{ref[:7]}", f"{repo}: {action}@{ref[:7]} is a commit at a ref tip.")
                else:
                    unjudged += 1
                    c.ok(
                        f"c21.not-at-a-tip:{repo}:{action}:{ref[:7]}",
                        f"{repo}: {action}@{ref[:7]} is at no ref tip of {action} (an older commit, or a tag since deleted); not a tag object, not judged further.",
                    )
    if subjects == 0 and unread == 0:
        c.missing(
            "c21.no-subjects",
            "no workflow in the estate uses an action, so this gate measured nothing; two dozen repositories do, "
            "so finding none means this check read the wrong thing.",
        )
    elif unjudged:
        c.note(f"{unjudged} pin(s) are commits at no ref tip and were not judged beyond that.")
    return c


def _peeled_commit_for(refs: ActionRefs, action: str, tag_object_sha: str) -> str | None:
    """The commit an annotated tag object points to, from the same ls-remote."""
    if refs.fixture is not None:
        entry = refs.fixture.get(action, {})
        return entry.get(f"{tag_object_sha}^{{}}")
    proc = subprocess.run(
        ["git", "ls-remote", "--tags", f"https://github.com/{action}"],
        capture_output=True,
        text=True,
        timeout=60,
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
    )
    if proc.returncode != 0:
        return None
    name = None
    for line in proc.stdout.splitlines():
        sha, _, ref = line.partition("\t")
        if sha == tag_object_sha and ref.startswith("refs/tags/") and not ref.endswith("^{}"):
            name = ref
    if name is None:
        return None
    for line in proc.stdout.splitlines():
        sha, _, ref = line.partition("\t")
        if ref == name + "^{}":
            return sha
    return None


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    E.add_common_args(p)
    args = p.parse_args()
    estate = E.estate_from_args(args)
    return run(estate).render()


if __name__ == "__main__":
    sys.exit(main())
