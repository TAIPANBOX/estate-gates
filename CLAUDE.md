# CLAUDE.md, working instructions for estate-gates

These instructions apply to any model working in this repo. Read this file
before changing anything. It holds process and invariants only: **no status.**
Status goes stale, and a stale instruction file is worse than none. For what
the checks found, run them.

## What this repo is

The cross-repo gate suite. Checks that each compare two or more OTHER
repositories in the estate, plus a self-test that proves each of them can
fail. How many there are is not written here: it is a number that moves, and
this file holds no status. `GATES` in `run-gates.py` is the list.

**It is the only repository allowed to know about more than one repository at
once**, and that is its whole reason to exist. Every other repo in the estate
gates itself well and none of them can see the space between them, which is
where the estate's real defects have lived.

## Read before you change anything

1. `README.md`, in full. It states the two rules, what each check does, and
   what is deliberately not covered. The last of those is the part people
   assume rather than read.
2. `selftest.py`. Understand the mutation harness before adding a check,
   because a check without a mutation will not get past it.
3. `selftest/fixture.py`, the miniature estate everything is proved against.
4. `expectations/deployment-parity.json`, which is a decision record, not
   configuration.

## This repository READS other repositories and never writes to them

Never edit, commit to, or push a sibling checkout from here. When a check
finds drift, the fix belongs in the repository that drifted, opened as its own
change with its own review. A gate that fixes what it measures is a gate
measuring its own output.

Prefer `--mode ref --ref origin/main` when correctness matters. Sibling
working trees may be mid-edit by somebody else, and a finding read out of
somebody's uncommitted work is a finding they did not make yet.

## The working loop

1. Branch off `main`, one logical increment per branch.
2. Run the gates below. All must pass.
3. Commit with Conventional Commits. End the message with the standard
   co-author trailer naming the model that actually did the work.
4. Push the branch, open a PR with `gh`.
5. Wait for CI to go green.
6. **Ask the user before merging.** Do not self-merge.

## Gates

```sh
./selftest.py
./scripts/no-long-dashes.sh --prove
./run-gates.py --mode ref --ref origin/main
```

CI runs the first two and then `./run-gates.py --mode clone`. The third is
allowed to be red: it is a report about the estate.

## Hard invariants

Each carries how it is held today. Use `(gate: ...)`, `(test: ...)`,
`(partly gated: ...)` or `(not enforced)`, and use the weakest one that is
true. An invariant with no check, written as though it had one, is worse than
an absent invariant.

1. **Every check must be proven capable of failing.** A check that cannot fail
   is worse than no check, because it reports green forever and somebody
   trusts it. `selftest.py` builds a miniature estate, breaks one thing at a
   time, and requires the matching finding to fire. It also reads every gate's
   AST for `c.drift(...)` and `c.missing(...)` calls, so a FAIL path added
   without a mutation fails the self-test, and a mutation left behind for a
   finding that no longer exists fails it too.

   **Where a check ANDs, or claims to be stricter than the obvious
   comparison, one case is not enough.** C2 had a single mutation that renamed
   a field, and rewriting C2 to compare tokens instead of bytes left every
   mutation firing and the self-test green while the check had stopped
   enforcing the byte-identity its own docstring argues for. A mutation a
   WEAKENED check still catches proves the check runs, not that it checks.
   *(gate: `selftest.py`; verified by adding a `c.drift` with no mutation,
   which fails it, and by weakening C2 two ways, both of which now fail it)*

2. **A check whose subject has vanished fails loudly.** A missing file, an
   absent repository or an anchor that matches nothing is a red naming what
   disappeared, never a skip and never a pass. `_estate.Missing` exists so
   those three arrive at the same place, and `Check.verdict` returns red for a
   check that produced no findings at all.
   *(gate: `selftest.py`; twelve of the mutations delete a subject or rename
   an anchor)*

3. **A repository nobody could read is never reported as agreement.** Distinct
   from invariant 2: this is about the RUN, not the estate. An unreadable repo
   downgrades its check to PARTIAL, names itself in the summary, and gives the
   run its own exit code. Only repositories `estate.json` records as having no
   public remote may end a run at exit 3.

   The distinction has teeth in both directions. C5 used to report
   `too-few-deployments` as red when all three deployment repos were merely
   unreachable, which said the estate was broken when the truth was that
   nothing had looked.
   *(gate: `selftest.py` removes taipan and requires PARTIAL plus a
   NOT MEASURED line, and separately produces all four of the runner's exit
   codes from real runs. Exit 3 had never been returned by anything until that
   test was written, because every real run so far had also found drift, and
   CI reads the exit code and nothing else.)*

4. **Every failure names BOTH SIDES, with a path a reader can open.** A
   finding that says two things disagree without saying where they live is a
   search task, and a reader who has to go looking will stop reading.
   *(not enforced: this is prose in every message and nothing checks it. The
   nearest structural help is that `Estate.where` exists and takes both a repo
   and a path, so the easy thing to write is the correct thing.)*

5. **Nothing here writes to another repository.** This suite reads. The fix
   for a finding belongs in the repository that drifted.
   *(not enforced: no check opens a file for writing outside this repo today,
   and nothing stops one being added)*

6. **The output says what it read.** Every run prints its mode, and C3 prints
   which of its two sources it used. A comparison whose reader does not know
   what was compared is one somebody will quote wrongly later.
   *(partly gated: `Check.render` always prints `estate.label()`, so the mode
   cannot be omitted. C3's mode line is a `c.note` call that nothing enforces.)*

7. **A divergence between the three deployments is either recorded with a
   reason or red.** And an expectation recorded for a divergence that no
   longer exists is red as well, so the file cannot become a graveyard.
   *(gate: `gates/c5-deployment-parity.py`; verified by four unrecorded
   divergences, one per fact family, and by one stale expectation)*

8. **Dependency-free.** python3, bash and git. The estate's gate scripts are
   dependency-free by conviction, and a suite that needs `pip install` before
   it can say the estate is broken is a suite that runs less often.
   *(not enforced: no import outside the standard library today)*

9. **Nothing metered.** This repository is public, so standard-runner Actions
   minutes and the nightly cron cost nothing. A matrix, a larger runner, a
   self-hosted runner or any paid service is a spending decision and needs the
   user's agreement first, in advance.
   *(not enforced: the reason is written at the top of the workflow, where
   somebody about to add a matrix will read it)*

10. **No long dashes** anywhere in this repository.
    *(gate: `scripts/no-long-dashes.sh`, which decodes bytes in python rather
    than trusting a grep build; `--prove` plants one and requires itself to
    find it)*

## Decisions that have no gate yet

This list is debt, and it is here to stay visible rather than to be tidy.

**Held by this file alone: invariants 4, 5, 8 and 9.**

- **The fixture is not the estate.** `selftest.py` proves the machinery: each
  check can see a break, can pass a clean estate, and fails loudly on a
  missing subject. It does NOT prove that the shapes in
  `selftest/fixture.py` still resemble the real repositories. What catches an
  anchor going stale in the real estate is the nightly run, where an anchor
  that matches nothing is a FAIL by construction. Keep it that way: an anchor
  that degrades to a skip would make the fixture the only thing being
  measured.
- **There is no coverage check.** Nothing links "repositories in
  `estate.json`" to "repositories some gate actually reads". A repository
  could join the estate and be covered by nothing. The honest fix is for each
  gate to report the repos it touched and for the runner to compare that with
  the registry; it is not built.
- **`expectations/deployment-parity.json` is @claude throughout.** Every
  reason in it is my reading of the three deployment repositories on
  2026-08-06, not a decision anybody stated. Several entries say plainly that
  the divergence is a gap rather than a decision. Do not promote any of them
  to `@yurii` without the user's words, and do not quietly reword one into
  sounding decided.
- **C4's Rust, Go and Python parsers are anchors, not compilers.** Each is
  narrow on purpose and each fails loudly when it stops matching, which is the
  best available answer, not a good one. The real answer is what tokenfuse is
  doing with `contracts/tokenfuse-constants.json`: a producer that PUBLISHES
  its vocabulary as a generated artifact needs no parser at all. Every time a
  repository does that, delete the parser here.

## Standing rule

An approved architecture decision is **not finished** until it is two things:
a numbered invariant in this file, and a gate in a script if it can be checked
structurally. Until then it is a document, and documents do not stop code.

## Escalate, do not push through

Stop and tell the user, then wait:

- Weakening a check so that a red run goes green. A red here is a finding
  about the estate, and the fix is in the repository that drifted. This is the
  one change that would make this repository worthless.
- Adding a matrix, a larger runner, or any metered service to the workflow.
- Recording a new divergence in `expectations/deployment-parity.json` as
  DELIBERATE when it might be a gap. Recording it as a gap needs nobody;
  calling it a decision is a claim about what somebody decided.
- Changing an `agreed` value in the expectations file. That is a statement
  about what the product is, not a way to make a check pass.

## Conventions

- **No long dashes** anywhere: not in code, docs, JSON, commit messages or PR
  bodies. Use a comma, a colon, parentheses, or a short hyphen.
- Nothing paid or metered gets enabled without telling the user first and
  getting agreement.
- Do not delete or revoke keys, tokens or certificates on your own initiative.

11. **A check about a trust boundary belongs on the side that can see across
    it.** wardryx believes `chain_proven` and says so in its own comment. That
    is the right design: a PDP deciding at 3.2 ms p50 must not verify a
    signature per decision. It also means no amount of care inside wardryx can
    tell a verified claim from an asserted one, because the evidence is in
    another repository.

    This repository is where that evidence meets the claim, and C11 is the
    shape: for every producer, does the file that asserts also call. It
    generalises past this one field. Any time a plane documents "the caller is
    believed here", ask what would notice a caller who lied, and if the answer
    is nothing, the check belongs in this repository rather than in either of
    theirs. *(gate: `gates/c11-proven-means-verified.py`, with three cases in
    `selftest.py`: an assertion with no verifier, a verifier left in an import
    and a comment with the call gone, and the field vanishing from the estate
    entirely, which is the "measured nothing" answer rather than a clean one.)*

