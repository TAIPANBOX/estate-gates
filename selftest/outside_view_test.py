#!/usr/bin/env python3
"""Unit checks for scripts/outside-view.py's pure helpers.

Written 2026-11-27, red first: the image table printed "latest v1.14.0" for
tokenfuse-dashboard while v1.27.0 was published, because the registry pages
its tag list at 100 and the script took the last entry of the first page, in
alphabetical order. It also counted a template's placeholder tag
(agent-example:replace-with-a-pinned-tag) as a pinned image that fails an
anonymous pull, and it read manifests inside .claude/worktrees.
"""
import importlib.util, pathlib, sys, tempfile

here = pathlib.Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("ov", here / "scripts" / "outside-view.py")
ov = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ov)

fails = 0
def check(name, got, want):
    global fails
    ok = got == want
    fails += not ok
    print(f"{'ok  ' if ok else 'FAIL'} {name}: got {got!r}" + ("" if ok else f", want {want!r}"))

tags = [f"v1.{i}.0" for i in range(10, 28)] + ["sha-cdda43e", "latest", "v1.9.0", "sha256-abc.sig"]
check("highest version, not the last listed", ov.highest_version(tags), "v1.27.0")
check("no version tag at all", ov.highest_version(["sha-1", "latest"]), None)
check("placeholder tag", ov.is_placeholder("replace-with-a-pinned-tag"), True)
check("real tag is not a placeholder", ov.is_placeholder("v0.6.1"), False)

with tempfile.TemporaryDirectory() as d:
    d = pathlib.Path(d)
    (d / "repo" / "k8s").mkdir(parents=True)
    (d / "repo" / "k8s" / "a.yaml").write_text("image: ghcr.io/taipanbox/real:v1.0.0\nimage: ghcr.io/taipanbox/tmpl:replace-with-a-pinned-tag\n")
    (d / "repo" / ".claude" / "worktrees" / "x").mkdir(parents=True)
    (d / "repo" / ".claude" / "worktrees" / "x" / "b.yaml").write_text("image: ghcr.io/taipanbox/stray:v9.9.9\n")
    found = ov.scan_pinned(d / "repo", "repo")
    check("pinned images skip dot dirs and placeholders", sorted(found), ["real"])

sys.exit(1 if fails else 0)
