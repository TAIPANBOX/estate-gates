#!/usr/bin/env python3
"""C20: every install line a README publishes resolves to a release that
exists, and none of them names a moving tag.

WHY

tokenfuse's README said `docker run ... ghcr.io/taipanbox/tokenfuse` for two
months while `latest` in the registry was a July build: the release workflow
wrote `latest` only `enable={{is_default_branch}}`, which a tag push never
satisfies, so every tag after v0.3.0 published its own tag and left `latest`
where it was. The one-liner on the front page installed a version nobody had
released for weeks, and nothing could see it, because the line was correct as
a command and wrong as a claim (PUBLISH-READINESS 2026-09-12, 1.1).

The estate's answer, decided 2026-08-02 for four planes and taken everywhere
on 2026-09-12 (RELEASE-1.0-PLAN decision 10.26, route A): no moving tag. A
README pins the tag it means, and this gate holds the pin against the
repository's own tags and releases, so the day a new tag is cut the README is
red until the line is bumped, the same stance C1 takes for a module pin.

WHAT IS READ

`README.md` of every repository `estate.json` names, and in it two shapes:

  ghcr.io/taipanbox/<image>[:<tag>]
  github.com/TAIPANBOX/<repo>/releases/download/<tag>/<asset>
  github.com/TAIPANBOX/<repo>/releases/latest/download/<asset>

A line carrying a placeholder (`<name>`, `$V`, `${tag}`) is a template a reader
fills in, not a link, and is skipped. Nothing outside README.md is read: the
design documents quote old commands as history, and a gate that judged them
would be red on purpose forever.

WHAT COUNTS AS A FAILURE

  c20.image-unpinned   an image with no tag pulls whatever `latest` is, and
                       under route A there is no `latest`. Allowed only when
                       the owning repository's estate.json entry says
                       `"moving_tag": true`, which today none does.
  c20.image-unowned    an image name no repository in estate.json owns: a
                       typo, or an image this estate does not publish
  c20.tag-unknown      the pinned tag is not a git tag of the owning
                       repository (a `-variant` suffix such as `-chromium` or
                       `-cluster` is stripped first: the base tag is the one
                       cut)
  c20.repo-unknown     a releases URL naming a repository estate.json does not
  c20.release-missing  `releases/download/<tag>/` for a tag with no Release
                       object: the URL is a 404 until somebody creates one
  c20.no-releases      `releases/latest/download/` in a repository with no
                       Release at all
  c20.no-subjects      no README in the estate carries an install line, so
                       this gate measured nothing; the estate has a dozen that
                       do, so measuring none means this check read the wrong
                       thing

HOW IMAGES ARE MAPPED TO REPOSITORIES

By name: the owner is the repository whose name is the longest prefix of the
image name (`tokenfuse-control-plane` is tokenfuse's, `trailryx-node` is
trailryx's, `genaryx-console` is genaryx's). Nothing is hand-listed; a new
image named after its repository is owned the day it appears.

HOW RELEASES ARE READ

Through the GitHub API (`gh api repos/TAIPANBOX/<repo>/releases`), once per
repository per run. The self-test exports a fixture instead through
`ESTATE_GATES_RELEASES` (a JSON object, repository to the list of tags that
have a Release), the same way C18 takes its expectations; a real run never
sets it. When the API cannot be reached the finding is UNAVAILABLE, not OK.

WHAT IT DOES NOT CATCH

Whether the image tag exists in the REGISTRY: a git tag is the necessary
condition this gate can read offline, and `scripts/outside-view.py` asks the
registry itself. Whether a downloaded asset name exists on the Release (the
Release is checked, its asset list is not). And any install line written in a
shape these two patterns do not match.
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

OWNER = "taipanbox"
GITHUB_OWNER = "TAIPANBOX"
_IMAGE = re.compile(rf"ghcr\.io/{OWNER}/([a-z0-9][a-z0-9._-]*)(?::([A-Za-z0-9][A-Za-z0-9._-]*))?")
_DOWNLOAD = re.compile(
    rf"github\.com/{GITHUB_OWNER}/([A-Za-z0-9._-]+)/releases/(?:download/([A-Za-z0-9._-]+)|(latest)/download)/"
)
_PLACEHOLDER = re.compile(r"[<$\{]")
_VARIANT = re.compile(r"^(v\d+\.\d+\.\d+)-[A-Za-z0-9._-]+$")


class Releases:
    """Tags that have a Release object, per repository, read once."""

    def __init__(self) -> None:
        fixture = os.environ.get("ESTATE_GATES_RELEASES")
        self.fixture = json.loads(pathlib.Path(fixture).read_text()) if fixture else None
        self.cache: dict[str, list[str] | None] = {}

    def tags_with_release(self, repo: str) -> list[str] | None:
        """The tag names with a Release, or None when the API could not answer."""
        if self.fixture is not None:
            return list(self.fixture.get(repo, []))
        if repo in self.cache:
            return self.cache[repo]
        proc = subprocess.run(
            ["gh", "api", f"repos/{GITHUB_OWNER}/{repo}/releases", "--paginate", "-q", ".[].tag_name"],
            capture_output=True,
            text=True,
            timeout=120,
        )
        result = None if proc.returncode != 0 else [t for t in proc.stdout.split() if t]
        self.cache[repo] = result
        return result


def image_owner(image: str, repos: list[str]) -> str | None:
    """The repository whose name is the longest prefix of the image name."""
    best = None
    for repo in repos:
        if image == repo or image.startswith(repo + "-"):
            if best is None or len(repo) > len(best):
                best = repo
    return best


def run(estate: E.Estate) -> E.Check:
    c = E.Check("C20", "every README install line resolves to a release that exists", estate)
    releases = Releases()
    repos = sorted(estate.repos)
    subjects = 0
    unread = 0
    tags_cache: dict[str, set[str]] = {}

    def tags_of(repo: str) -> set[str]:
        if repo not in tags_cache:
            tags_cache[repo] = set(estate.tags(repo))
        return tags_cache[repo]

    for repo in repos:
        try:
            text = estate.read_text(repo, "README.md")
        except E.Missing:
            continue
        except E.Unavailable as u:
            c.unavailable(f"c20.readme-unavailable:{repo}", str(u))
            unread += 1
            continue

        for lineno, line in enumerate(text.splitlines(), start=1):
            where = f"{estate.where(repo, 'README.md')} line {lineno}"

            for m in _IMAGE.finditer(line):
                image, tag = m.group(1), m.group(2)
                subjects += 1
                owner = image_owner(image, repos)
                if owner is None:
                    c.drift(
                        "c20.image-unowned",
                        f"{repo}'s README names ghcr.io/{OWNER}/{image}, an image no repository in estate.json owns.",
                        [f"  {where}", "A typo, or an image this estate does not publish."],
                    )
                    continue
                if tag is None:
                    if estate.repos[owner].get("moving_tag"):
                        c.ok(f"c20.moving-tag-declared:{owner}", f"{repo}: {image} without a tag; {owner} declares a moving tag.")
                        continue
                    c.drift(
                        "c20.image-unpinned",
                        f"{repo}'s README names ghcr.io/{OWNER}/{image} with no tag.",
                        [
                            f"  {where}",
                            f"Without a tag `docker run` pulls `latest`, and {owner} publishes none",
                            "(route A, decision 10.26). Pin the newest tag; this gate turns red the day",
                            "a newer one is cut, which is when the line needs bumping.",
                        ],
                    )
                    continue
                if _PLACEHOLDER.search(tag):
                    continue
                base = _VARIANT.sub(r"\1", tag)
                try:
                    known = tags_of(owner)
                except (E.Missing, E.Unavailable) as u:
                    c.unavailable(f"c20.tags-unavailable:{owner}", str(u))
                    continue
                if base in known:
                    c.ok(f"c20.image:{repo}:{image}:{tag}", f"{repo}: {image}:{tag} is a tag {owner} cut.")
                else:
                    c.drift(
                        "c20.tag-unknown",
                        f"{repo}'s README pins ghcr.io/{OWNER}/{image}:{tag}, and {owner} has no tag {base}.",
                        [f"  {where}", f"  {owner}'s tags: {', '.join(sorted(known)) or '(none)'}"],
                    )

            for m in _DOWNLOAD.finditer(line):
                target, tag, latest = m.group(1), m.group(2), m.group(3)
                subjects += 1
                if target not in estate.repos:
                    c.drift(
                        "c20.repo-unknown",
                        f"{repo}'s README links a release of {GITHUB_OWNER}/{target}, which estate.json does not name.",
                        [f"  {where}"],
                    )
                    continue
                have = releases.tags_with_release(target)
                if have is None:
                    c.unavailable(f"c20.releases-unavailable:{target}", f"the GitHub API did not answer for {target}'s releases")
                    continue
                if latest:
                    if have:
                        c.ok(f"c20.latest:{repo}:{target}", f"{repo}: releases/latest of {target} resolves ({len(have)} release(s)).")
                    else:
                        c.drift(
                            "c20.no-releases",
                            f"{repo}'s README links releases/latest/download of {target}, which has no Release.",
                            [f"  {where}", "The URL is a 404 until a Release object exists (gh release create --verify-tag)."],
                        )
                    continue
                if tag is None or _PLACEHOLDER.search(tag):
                    continue
                if tag in have:
                    c.ok(f"c20.download:{repo}:{target}:{tag}", f"{repo}: releases/download/{tag} of {target} exists.")
                else:
                    try:
                        is_tag = tag in tags_of(target)
                    except (E.Missing, E.Unavailable):
                        is_tag = False
                    c.drift(
                        "c20.release-missing",
                        f"{repo}'s README links releases/download/{tag} of {target}, and no Release exists for that tag"
                        + (" (the git tag exists)." if is_tag else " (nor the git tag)."),
                        [f"  {where}", f"  releases of {target}: {', '.join(sorted(have)) or '(none)'}"],
                    )

    # As in C19: a run that could not read a README has not established that
    # no README carries an install line.
    if subjects == 0 and unread == 0:
        c.missing(
            "c20.no-subjects",
            "no README in the estate carries an install line this gate reads, so it "
            "measured nothing. A dozen repositories publish one, so finding none means "
            "this check read the wrong thing rather than that nothing is installed.",
        )
    return c


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    E.add_common_args(p)
    args = p.parse_args()
    estate = E.estate_from_args(args)
    return run(estate).render()


if __name__ == "__main__":
    sys.exit(main())
