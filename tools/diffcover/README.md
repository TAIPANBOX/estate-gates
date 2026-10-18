# diffcover

The coverage floor on what a change adds, for any repository in the estate
(CLAUDE.md invariant 27). Go standard library only, one static binary, and no
`go.mod` require line, so a caller builds it from a pinned commit of this
repository and nothing else.

```sh
go build -o diffcover .
diffcover -C <repo> -base <base-sha> -coverage cover.out -format gocover
```

It reads three things and prints what it measured:

1. **The coverage file.** LCOV (`cargo llvm-cov --lcov`, `coverage lcov`) with
   `-format lcov`, the default; or a `go test -coverprofile` profile with
   `-format gocover`.
2. **The diff.** `git diff --unified=0 base...HEAD`, or a file given by `-diff`.
   Only the lines the change adds are judged.
3. **`.coverage-baseline`** in the repository root: one percentage, the
   whole-repository floor. Missing or unreadable is an input error, not a pass.

## What is judged

- **Added executable lines** must reach `-threshold` (default 90), counted as
  covered lines over executable lines, in integers, so 9 of 10 is exactly 90.
- **Whole-repository line coverage** must not be below the baseline. It is
  compared exactly, so a baseline of `59.5` and a coverage of `59.49` fail.

## What counts as executable

- **LCOV:** a line is executable when the file lists it in a `DA` record.
  Hit counts from several records for one file add up.
- **Go profile:** a line is executable when a block with statements starts or
  ends on it. A comment or a continuation line in the middle of a block is not.
  The Go tool counts statements, not lines, so this is the line-level reading
  of it and it is approximate by construction.

## The exclusion rule

An added line is judged only when the coverage file names its file **and**
lists the line as executable. Any other added line is excluded:

- a file no coverage record names is excluded as a whole, and printed with its
  number of added lines, so a test, a document or a generated file does not
  count as code missing coverage;
- a line in a named file that the coverage file does not list as executable (a
  comment, a blank line) is not counted.

The consequence to plan for: a new source file that the coverage command never
instrumented is excluded too. For Go the workflow runs `go test -coverpkg=./...`
so every package is in the profile, tested or not.

## Measured nothing

Exit 3 and no verdict of pass. It happens when:

- the coverage file has no executable line at all (empty, or only records with
  no `DA` lines);
- the diff adds no lines;
- the coverage file names none of the files the diff touches;
- the added lines in named files are none of them executable.

A pull request that only changes documentation is measured nothing. A caller
that accepts those pull requests scopes its trigger with `paths:` or
`paths-ignore:`. The tool does not guess which files are code.

## Exit codes

`0` pass. `1` below the threshold or the baseline. `2` usage or input error (an
unreadable file, a malformed coverage record, an unknown base revision, a bad
baseline). `3` measured nothing.

## Renames and deletions

A renamed file with changes is judged under its new name. A pure rename adds no
lines. A deleted file adds nothing. Deleted lines add nothing and do not move
the numbering of the lines around them.

## Paths

A coverage path under `-C` is made relative to it, so an absolute path from a
coverage tool matches a diff path. `git` runs with fixed `a/` and `b/` prefixes
and `--relative`, and with `GIT_DIR`, `GIT_WORK_TREE` and the other repository
variables removed from its environment, because a pre-push hook sets `GIT_DIR`
to the repository being pushed.

## What it does not say

- **Whether a test checks anything.** Coverage counts execution. A covered line
  can be checked by an assertion that never fails, and nothing here can see
  that.
- **Branches.** Only lines, in both formats.
- **Files that no coverage command reaches.** See the exclusion rule.
- **LCOV beyond the hand-written tests.** The LCOV reader is proven by table
  rows and not yet by a run of `cargo llvm-cov` or `coverage lcov` on a real
  repository.

## Tests

```sh
GOTOOLCHAIN=local go test -race -count=1 ./...
```

The tests use hand-written LCOV, cover profiles and diffs, and one integration
test that makes a real git repository, commits a change and judges it. Each
table row states one rule. The rules were first run against stubs and failed
for the right reason, and five mutants of the implementation (a boundary moved,
deletions moving the numbering, a cover block marking every line, unnamed files
counted as uncovered, an empty coverage file passing) each made at least two
tests fail.
