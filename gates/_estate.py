"""Shared machinery for the cross-repo gates: where a file comes from, and how
a finding is said out loud.

Two rules govern everything in this module, and both are about the same
failure: a check that reports green when it measured nothing.

RULE 1, a check that cannot fail is worse than no check. Nothing here is
allowed to swallow an error. `read_text` raises rather than returning "" and
every caller turns that into a red.

RULE 2, a subject that has vanished is a red, never a pass. `Missing` exists
so that "the file is gone", "the repo is not checked out" and "the anchor
matched nothing" all arrive at the same place: a finding that names what
disappeared.

WHERE FILES COME FROM

Three modes, because the same check has to answer three different questions:

  worktree   what is on this developer's disk right now. The default locally.
             Sibling checkouts may be mid-edit, on a branch, or dirty, and
             that is the point: it is the state somebody is about to push.
  ref:REF    what a git ref holds, read with `git show REF:path`. Use
             `--ref origin/main` to ask about the estate as published, which
             is the question worth asking while eight agents are editing.
  clone      fresh shallow clones of the public repos. What CI uses.

Every run prints which mode it used. A finding that does not say what it read
is a finding nobody can reproduce.
"""

from __future__ import annotations

import difflib
import json
import os
import pathlib
import re
import subprocess
import sys

# ---------------------------------------------------------------- exceptions


class Missing(Exception):
    """A subject a check needs is not there.

    Never caught and turned into a pass. Callers translate it into a `missing`
    finding, which is red.
    """


class Unavailable(Exception):
    """A repository this run cannot reach, for a reason recorded in
    estate.json.

    Distinct from `Missing` on purpose. `Missing` means the estate is wrong;
    this means this RUN could not look. It never reads as a pass either: it
    downgrades the check to PARTIAL and the runner prints what went unmeasured.
    """

    def __init__(self, repo: str, reason: str):
        super().__init__(f"{repo}: {reason}")
        self.repo = repo
        self.reason = reason


# ------------------------------------------------------------------- estate

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent


def load_registry(path: pathlib.Path | None = None) -> dict:
    path = path or (REPO_ROOT / "estate.json")
    if not path.is_file():
        raise Missing(f"{path} is not there, so no check knows what the estate is")
    return json.loads(path.read_text(encoding="utf-8"))


class Estate:
    """Resolves `repo, relative/path` to text, in one of the three modes."""

    def __init__(
        self,
        registry: dict,
        mode: str = "worktree",
        ref: str | None = None,
        root: pathlib.Path | None = None,
        cache: pathlib.Path | None = None,
    ):
        self.registry = registry
        self.repos: dict = registry["repos"]
        self.mode = mode
        self.ref = ref
        self.root = pathlib.Path(root) if root else REPO_ROOT.parent
        self.cache = pathlib.Path(cache) if cache else (REPO_ROOT / ".clones")
        self._cloned: dict[str, pathlib.Path | None] = {}
        self._unavailable: dict[str, str] = {}

    # -- description -------------------------------------------------------

    def label(self) -> str:
        if self.mode == "clone":
            return f"fresh shallow clones under {self.cache}"
        if self.mode == "ref":
            return f"`git show {self.ref}:...` in the checkouts under {self.root}"
        return f"the working trees under {self.root}"

    def unavailable_repos(self) -> dict[str, str]:
        """Repos this run could not read, and why. Read by the runner."""
        return dict(self._unavailable)

    # -- resolution --------------------------------------------------------

    def _entry(self, repo: str) -> dict:
        try:
            return self.repos[repo]
        except KeyError:
            raise Missing(
                f"'{repo}' is not in estate.json, so a check is asking about a "
                f"repository this repository does not know exists"
            ) from None

    def dir_of(self, repo: str) -> pathlib.Path:
        """Where this repo's files are for this run. Raises Unavailable."""
        entry = self._entry(repo)
        if self.mode == "clone":
            return self._clone(repo, entry)
        local = self.root / entry.get("local", repo)
        if not (local / ".git").exists() and not local.is_dir():
            self._unavailable[repo] = f"no checkout at {local}"
            raise Unavailable(repo, f"no checkout at {local}")
        return local

    def _clone(self, repo: str, entry: dict) -> pathlib.Path:
        if repo in self._cloned:
            got = self._cloned[repo]
            if got is None:
                raise Unavailable(repo, self._unavailable[repo])
            return got
        slug = entry.get("github")
        if not slug:
            why = entry.get(
                "why_no_remote", "estate.json records no public remote for it"
            )
            self._unavailable[repo] = why
            self._cloned[repo] = None
            raise Unavailable(repo, why)
        dest = self.cache / repo
        if not dest.is_dir():
            dest.parent.mkdir(parents=True, exist_ok=True)
            url = f"https://github.com/{slug}.git"
            proc = subprocess.run(
                ["git", "clone", "--depth", "1", "--quiet", url, str(dest)],
                capture_output=True,
                text=True,
            )
            if proc.returncode != 0:
                why = f"git clone {url} failed: {proc.stderr.strip().splitlines()[-1:] or ''}"
                self._unavailable[repo] = why
                self._cloned[repo] = None
                raise Unavailable(repo, why)
            # Tags are what C1 compares against and --depth 1 does not fetch
            # them. Without this the newest tag reads as "none" and C1 would
            # report every consumer current, which is rule 1's exact failure.
            subprocess.run(
                ["git", "-C", str(dest), "fetch", "--tags", "--quiet", "--depth", "1"],
                capture_output=True,
                text=True,
            )
        self._cloned[repo] = dest
        return dest

    # -- reading -----------------------------------------------------------

    def read_text(self, repo: str, relpath: str) -> str:
        """The text of one file. Raises Missing if it is not there."""
        return self.read_bytes(repo, relpath).decode("utf-8")

    def read_bytes(self, repo: str, relpath: str) -> bytes:
        directory = self.dir_of(repo)
        if self.mode == "ref":
            proc = subprocess.run(
                ["git", "-C", str(directory), "show", f"{self.ref}:{relpath}"],
                capture_output=True,
            )
            if proc.returncode != 0:
                raise Missing(
                    f"{repo}:{relpath} does not exist at {self.ref} "
                    f"({proc.stderr.decode('utf-8', 'replace').strip()})"
                )
            return proc.stdout
        path = directory / relpath
        if not path.is_file():
            raise Missing(f"{repo}:{relpath} does not exist ({path})")
        return path.read_bytes()

    def exists(self, repo: str, relpath: str) -> bool:
        try:
            self.read_bytes(repo, relpath)
            return True
        except Missing:
            return False

    def list_files(self, repo: str, suffix: str = "") -> list[str]:
        """Every tracked path in the repo, optionally filtered by suffix."""
        directory = self.dir_of(repo)
        if self.mode == "ref":
            args = ["git", "-C", str(directory), "ls-tree", "-r", "--name-only", self.ref]
        else:
            args = ["git", "-C", str(directory), "ls-files"]
        proc = subprocess.run(args, capture_output=True, text=True)
        if proc.returncode != 0:
            raise Missing(f"{repo}: could not list files ({proc.stderr.strip()})")
        names = [n for n in proc.stdout.splitlines() if n]
        if suffix:
            names = [n for n in names if n.endswith(suffix)]
        return names

    def tags(self, repo: str) -> list[str]:
        directory = self.dir_of(repo)
        proc = subprocess.run(
            ["git", "-C", str(directory), "tag"], capture_output=True, text=True
        )
        if proc.returncode != 0:
            raise Missing(f"{repo}: could not list tags ({proc.stderr.strip()})")
        return [t.strip() for t in proc.stdout.splitlines() if t.strip()]

    def where(self, repo: str, relpath: str) -> str:
        """A path a reader can open. Used in every failure message."""
        entry = self.repos.get(repo, {})
        if self.mode == "ref":
            return f"{entry.get('local', repo)}:{relpath} at {self.ref}"
        try:
            return str(self.dir_of(repo) / relpath)
        except Unavailable:
            return f"{repo}/{relpath}"


# ------------------------------------------------------------------ reporting

OK = "ok"
DRIFT = "drift"
MISSING = "missing"
UNAVAILABLE = "unavailable"

EXIT_CLEAN = 0
EXIT_DRIFT = 1
EXIT_INCOMPLETE = 2


class Check:
    """One gate's findings, and how they are printed.

    Every red path carries an ID. `selftest.py` reads those IDs out of this
    package's AST and refuses a red path that has no mutation proving it can
    fire. So an ID is not a label: it is the unit the self-test counts.
    """

    def __init__(self, key: str, title: str, estate: Estate):
        self.key = key
        self.title = title
        self.estate = estate
        self.findings: list[tuple[str, str, str, list[str]]] = []
        self.notes: list[str] = []
        self.measured = 0

    # -- findings ----------------------------------------------------------

    def ok(self, ident: str, message: str) -> None:
        self.measured += 1
        self.findings.append((OK, ident, message, []))

    def drift(self, ident: str, message: str, detail: list[str] | None = None) -> None:
        """The two sides disagree. Red."""
        self.measured += 1
        self.findings.append((DRIFT, ident, message, detail or []))

    def missing(self, ident: str, message: str, detail: list[str] | None = None) -> None:
        """A subject is gone, or an anchor matched nothing. Red, loudly.

        Separate from `drift` because the reader's next move differs: drift is
        fixed in one of the two repos, a missing subject means this check no
        longer knows what it is looking at and the check itself needs a change.
        """
        self.measured += 1
        self.findings.append((MISSING, ident, message, detail or []))

    def unavailable(self, ident: str, message: str) -> None:
        """This run could not look. Not a pass, not a drift."""
        self.findings.append((UNAVAILABLE, ident, message, []))

    def note(self, line: str) -> None:
        """A sentence about HOW the check ran, printed with the result.

        C3 uses this to say whether it read the published artifact or parsed
        the Rust. A comparison that does not say what it compared is one
        somebody will misread later.
        """
        self.notes.append(line)

    # -- verdict -----------------------------------------------------------

    def verdict(self) -> str:
        kinds = {f[0] for f in self.findings}
        if DRIFT in kinds or MISSING in kinds:
            return DRIFT
        if UNAVAILABLE in kinds:
            return UNAVAILABLE
        if not self.findings:
            # A check with nothing to say measured nothing. Rule 1.
            return MISSING
        return OK

    def exit_code(self) -> int:
        v = self.verdict()
        if v in (DRIFT, MISSING):
            return EXIT_DRIFT
        if v == UNAVAILABLE:
            return EXIT_INCOMPLETE
        return EXIT_CLEAN

    # -- printing ----------------------------------------------------------

    def render(self, stream=sys.stdout) -> int:
        w = stream.write
        w(f"{self.key}: {self.title}\n")
        w(f"Read from {self.estate.label()}.\n")
        for line in self.notes:
            w(f"  {line}\n")
        w("\n")

        reds = [f for f in self.findings if f[0] in (DRIFT, MISSING)]
        greys = [f for f in self.findings if f[0] == UNAVAILABLE]
        greens = [f for f in self.findings if f[0] == OK]

        for kind, ident, message, detail in reds:
            w(f"FAIL [{ident}] {message}\n")
            for line in detail:
                w(f"       {line}\n")
        for _, ident, message, _ in greys:
            w(f"NOT MEASURED [{ident}] {message}\n")
        for _, ident, message, _ in greens:
            w(f"ok   [{ident}] {message}\n")

        w("\n")
        if not self.findings:
            w(
                "FAIL: this check produced no findings at all, so it measured "
                "nothing.\n      A silent check is the failure this repository "
                "exists to prevent.\n"
            )
            return EXIT_DRIFT
        if reds:
            w(
                f"{len(reds)} of {self.measured} comparisons disagree. Both sides of "
                f"each are named above,\nwith the file to open. This is a report "
                f"about the estate, not about this repo.\n"
            )
        elif greys:
            w(
                f"{len(greens)} comparisons agree and {len(greys)} could not be made "
                f"in this run.\nWhat went unmeasured is listed above; it is not a "
                f"pass.\n"
            )
        else:
            w(f"OK: {len(greens)} comparisons, every one of them agrees.\n")
        return self.exit_code()


# ------------------------------------------------------------------ helpers


def unified_first_difference(
    left: str, right: str, left_name: str, right_name: str, context: int = 2
) -> list[str]:
    """The first hunk of a unified diff, as lines.

    The whole diff of two schemas is a wall nobody reads. The first difference
    is the one somebody fixes.
    """
    diff = list(
        difflib.unified_diff(
            left.splitlines(),
            right.splitlines(),
            fromfile=left_name,
            tofile=right_name,
            lineterm="",
            n=context,
        )
    )
    if not diff:
        return []
    out: list[str] = []
    hunks = 0
    for line in diff:
        if line.startswith("@@"):
            hunks += 1
            if hunks > 1:
                out.append("... (further differences not shown)")
                break
        out.append(line)
    return out


_SEMVER = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")


def semver(tag: str) -> tuple[int, int, int] | None:
    m = _SEMVER.match(tag.strip())
    if not m:
        return None
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)))


def add_common_args(parser) -> None:
    parser.add_argument(
        "--mode",
        choices=["worktree", "ref", "clone"],
        default=os.environ.get("ESTATE_GATES_MODE", "worktree"),
        help="worktree: sibling checkouts as they are. ref: what a git ref "
        "holds. clone: fresh shallow clones (what CI uses).",
    )
    parser.add_argument(
        "--ref",
        default=os.environ.get("ESTATE_GATES_REF", "origin/main"),
        help="the git ref to read in --mode ref (default origin/main)",
    )
    parser.add_argument(
        "--root",
        default=os.environ.get("ESTATE_GATES_ROOT"),
        help="directory holding the sibling checkouts (default: this repo's parent)",
    )
    parser.add_argument(
        "--cache",
        default=os.environ.get("ESTATE_GATES_CACHE"),
        help="where --mode clone puts its clones",
    )
    parser.add_argument(
        "--registry",
        default=os.environ.get("ESTATE_GATES_REGISTRY"),
        help="path to estate.json (default: this repo's own)",
    )


def estate_from_args(args) -> Estate:
    registry = load_registry(
        pathlib.Path(args.registry) if getattr(args, "registry", None) else None
    )
    return Estate(
        registry,
        mode=args.mode,
        ref=args.ref,
        root=args.root,
        cache=args.cache,
    )
