#!/usr/bin/env python3
"""The estate as a stranger sees it, regenerated rather than remembered.

WHY THIS EXISTS

Every gate in this repository compares two things inside the estate. None of
them can answer the question that decides whether the estate can be shown to
anybody: what does a person outside it actually find?

That question was answered from memory on 2026-09-01 and answered wrong, four
times in one session:

  - "Discussions are off and there is nowhere to write" - issues were enabled
    on all 22 repositories the whole time.
  - "genaryx has no public image" - the image is published under
    `genaryx-console`, and the 403 came from asking the registry for a name
    nobody uses.
  - "stack-single has never been brought up whole" - it was installed on a
    clean AWS machine on 2026-08-02, and a scoped "not proven" line about one
    later variable had been generalised into a claim about the launcher.
  - "Linux was never tested" - three clouds, with evidence files.

Each of those is cheap to measure and expensive to recall. So this script
measures them, stamps the answer with the moment it was taken, and prints the
command that produced it. Nothing here is a judgement: it is a census.

THE RULE THIS ENFORCES ON ITSELF

The subject list is `estate.json` and nothing else. A hand-written list of
repositories inside this file would be the exact defect the registry exists to
prevent, and it would be invisible: a forgotten repository would simply not
appear, and the report would look complete.

Container images are read from the stack-k8s manifests, which PIN them, rather
than assembled from the repository name. That is the direct fix for the
`genaryx` mistake above: the manifests are the only place in the estate that
states an image name authoritatively, because they are the place that must be
right or nothing starts.

WHAT IT CANNOT DO

It reports what is published, not whether it works. A green line here means a
stranger can reach the artifact, never that the artifact is good. Anything
about behaviour needs a run, and runs are recorded in PROVEN.md beside this,
with their dates and their commands.

It also cannot see a component nobody declared. Only Engram's components.json
carries a `distribution` key, so for every other repository the question "where
is this published for a human to install" has no declared answer and this
script says so rather than guessing.
"""

from __future__ import annotations

import argparse
import datetime
import json
import pathlib
import re
import subprocess
import sys
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "estate.json"
GHCR_OWNER = "taipanbox"


def run(cmd: list[str], timeout: int = 60) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout or p.stderr).strip()
    except Exception as exc:  # noqa: BLE001
        return 1, f"{type(exc).__name__}: {exc}"


def gh_json(path: str, jq: str | None = None) -> object | None:
    cmd = ["gh", "api", path]
    if jq:
        cmd += ["--jq", jq]
    rc, out = run(cmd)
    if rc != 0:
        return None
    try:
        return json.loads(out) if not jq else out
    except json.JSONDecodeError:
        return out


def ghcr_public(image: str) -> tuple[bool, str]:
    """Anonymous pull check: exactly what a stranger's docker gets, no login."""
    tok_url = (
        f"https://ghcr.io/token?scope=repository:{GHCR_OWNER}/{image}:pull"
        f"&service=ghcr.io"
    )
    try:
        with urllib.request.urlopen(tok_url, timeout=20) as r:
            token = json.load(r).get("token", "")
    except Exception as exc:  # noqa: BLE001
        return False, f"token error: {type(exc).__name__}"
    req = urllib.request.Request(
        f"https://ghcr.io/v2/{GHCR_OWNER}/{image}/tags/list",
        headers={"Authorization": f"Bearer {token}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            tags = json.load(r).get("tags") or []
        return True, f"{len(tags)} tag(s), latest {tags[-1] if tags else 'none'}"
    except urllib.error.HTTPError as exc:
        return False, f"HTTP {exc.code}"
    except Exception as exc:  # noqa: BLE001
        return False, type(exc).__name__


def pinned_images(estate: dict) -> dict[str, list[str]]:
    """Image names as the manifests pin them. The manifests are authoritative:
    they are the file that must be right or the pod does not start."""
    found: dict[str, list[str]] = {}
    for repo, entry in estate["repos"].items():
        local = ROOT.parent / (entry.get("local") or repo)
        if not local.is_dir():
            continue
        for path in list(local.rglob("*.yaml")) + list(local.rglob("*.yml")):
            if ".git" in path.parts:
                continue
            try:
                text = path.read_text(errors="ignore")
            except OSError:
                continue
            for m in re.finditer(
                rf"ghcr\.io/{GHCR_OWNER}/([a-z0-9._-]+):([A-Za-z0-9._-]+)", text
            ):
                found.setdefault(m.group(1), []).append(f"{repo}:{path.name}")
    return found


def declared_distribution(estate: dict) -> dict[str, str | None]:
    out: dict[str, str | None] = {}
    for repo, entry in estate["repos"].items():
        local = ROOT.parent / (entry.get("local") or repo)
        manifest = local / "components.json"
        if not manifest.is_file():
            out[repo] = None
            continue
        try:
            out[repo] = json.loads(manifest.read_text()).get("distribution")
        except (OSError, json.JSONDecodeError):
            out[repo] = None
    return out


def render(estate: dict, gh=gh_json, ghcr=ghcr_public) -> tuple[str, bool]:
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines: list[str] = []
    w = lines.append
    w("# The estate from outside")
    w("")
    w(f"**Taken {stamp}.** Regenerated, never edited by hand:")
    w("")
    w("```")
    w("./scripts/outside-view.py --write OUTSIDE-VIEW.md")
    w("```")
    w("")
    w(
        "Subjects come from `estate.json`. Image names come from the manifests "
        "that pin them. Nothing in this file is recalled."
    )
    w("")

    # --- repositories -----------------------------------------------------
    w("## Repositories")
    w("")
    w("| repo | vis | stars | forks | issues | open | discussions | latest release | assets |")
    w("|---|---|---|---|---|---|---|---|---|")

    unmeasured: list[str] = []
    private_by_decision: list[tuple[str, str, str]] = []
    for repo, entry in sorted(estate["repos"].items()):
        slug = entry.get("github")
        if not slug:
            priv = entry.get("private_remote")
            if priv:
                meta = gh(f"/repos/{priv}")
                vis = meta.get("visibility", "unknown") if isinstance(meta, dict) else "unreachable"
                private_by_decision.append((repo, priv, str(vis)))
            unmeasured.append(f"{repo}: {entry.get('why_no_remote', 'no public remote')}")
            continue
        meta = gh(f"/repos/{slug}")
        if not isinstance(meta, dict):
            unmeasured.append(f"{repo}: GitHub API unreachable")
            continue
        rel = gh(f"/repos/{slug}/releases/latest")
        if isinstance(rel, dict) and "tag_name" in rel:
            tag = rel["tag_name"]
            assets = len(rel.get("assets") or [])
        else:
            tag, assets = "none", 0
        w(
            f"| {repo} | {meta.get('visibility')} | {meta.get('stargazers_count')} "
            f"| {meta.get('forks_count')} | {meta.get('has_issues')} "
            f"| {meta.get('open_issues_count')} | {meta.get('has_discussions')} "
            f"| {tag} | {assets} |"
        )

    if unmeasured:
        w("")
        w("**Not measured** (and therefore not clean):")
        for line in unmeasured:
            w(f"- {line}")
    w("")

    # --- private by decision ---------------------------------------------
    flipped = False
    if private_by_decision:
        w("## Private by decision")
        w("")
        w(
            "Repositories `estate.json` records as private on purpose "
            "(`private_remote`). A flip to public is silent everywhere else, so "
            "it is measured here and fails the run."
        )
        w("")
        for repo, slug, vis in private_by_decision:
            if vis == "private":
                w(f"- {repo} (`{slug}`): private, as decided")
            else:
                flipped = True
                w(f"- **FLIP: {repo} (`{slug}`) measured {vis}, and it must be private**")
        w("")

    # --- images -----------------------------------------------------------
    w("## Container images, as a stranger's docker sees them")
    w("")
    w(
        "Names are taken from every `ghcr.io/` reference pinned in the estate's "
        "own manifests, so this list cannot drift from what actually gets "
        "deployed. The pull is anonymous: no login, no token."
    )
    w("")
    w("| image | pinned by | anonymous pull |")
    w("|---|---|---|")
    for image, sources in sorted(pinned_images(estate).items()):
        ok, detail = ghcr(image)
        mark = "yes" if ok else "NO"
        src = ", ".join(sorted(set(sources))[:3])
        w(f"| `{image}` | {src} | {mark}, {detail} |")
    w("")

    # --- declared distribution -------------------------------------------
    w("## Where each repository says it is published")
    w("")
    w(
        "`distribution` in a repository's own `components.json`. A repository "
        "with none has not declared where a human installs it, and this script "
        "will not invent an answer."
    )
    w("")
    dist = declared_distribution(estate)
    declared = {k: v for k, v in dist.items() if v}
    silent = sorted(k for k, v in dist.items() if not v)
    for repo, value in sorted(declared.items()):
        w(f"- **{repo}**: `{value}`")
    w("")
    w(f"**Undeclared ({len(silent)} of {len(dist)}):** {', '.join(silent)}")
    w("")
    return "\n".join(lines), flipped


def selftest(estate: dict) -> int:
    """Plant a flip and require the report to catch it, and plant none and
    require silence. No network: both GitHub and the registry are faked."""
    subjects = [e["private_remote"] for e in estate["repos"].values() if e.get("private_remote")]
    if not subjects:
        print("selftest: measured nothing, no private_remote in estate.json")
        return 2

    def fake(vis: str):
        return lambda path, jq=None: {"visibility": vis, "stargazers_count": 0, "forks_count": 0,
                                      "has_issues": True, "open_issues_count": 0, "has_discussions": False}

    no_pull = lambda image: (True, "selftest")  # noqa: E731
    text, flipped = render(estate, gh=fake("public"), ghcr=no_pull)
    if not flipped or "FLIP:" not in text:
        print("selftest: FAIL, a private-by-decision repository measured public and nothing said so")
        return 1
    text, flipped = render(estate, gh=fake("private"), ghcr=no_pull)
    if flipped or "FLIP:" in text:
        print("selftest: FAIL, a private repository was reported as a flip")
        return 1
    print(f"selftest: OK, a flip of any of {len(subjects)} private-by-decision repositories is caught, and none is invented")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", metavar="PATH", help="also write the report here (default: print only)")
    ap.add_argument("--selftest", action="store_true", help="prove the private-by-decision check can fail, without the network")
    args = ap.parse_args()

    estate = json.loads(REGISTRY.read_text())
    if args.selftest:
        return selftest(estate)
    text, flipped = render(estate)
    print(text)
    if args.write:
        pathlib.Path(args.write).write_text(text + "\n")
        print(f"\nwritten to {args.write}", file=sys.stderr)
    if flipped:
        print("\nFAIL: a repository that must be private is not. See 'Private by decision' above.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
