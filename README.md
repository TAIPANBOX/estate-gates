# estate-gates

The only repository in the TAIPANBOX estate allowed to know about more than
one repository at once.

## Why it exists

Sixteen repositories, each with unusually good gate discipline. Each names its
invariants. Each has scripts that fail a push when a claim stops being true.
Every one of them green.

A day of auditing found that almost every real defect was between them, where
no gate could see:

- verdryx held seven of tokenfuse's nine Breaker block-decision wire strings,
  so for eleven days it counted avoided estimates as real money;
- agent-stack-go's vendored copy of the passport schema fell three weeks
  behind the canonical one, so its "full schema validation" silently skipped
  the two fields that exist for AI Act code inventory;
- agent-passport's registry said idryx emits events; idryx has no event writer
  at all, and three artifacts carried that claim for weeks after the prose was
  corrected;
- idryx pinned agent-stack-go v0.3.0 while the module was at v0.5.1, and the
  entire delta was the tamper-evidence chain verifier idryx most needed;
- the same stack is deployed three ways and they disagree on which governance
  routines run, on a severity default, and on which components come up.

None of those is a bug inside a repository. Every one is a disagreement
between two of them, and a single-repo gate cannot have an opinion about a
file it is not allowed to read. This repository is the answer to that class,
and it is the only place with that permission.

## The two rules

**1. A check that cannot fail is worse than no check**, because it reports
green forever and somebody trusts it. Every check here is proven capable of
failing by `./selftest.py`, which builds a miniature estate, breaks one thing
at a time, and requires the matching finding to fire. It also reads the gates'
own AST, so a FAIL path added tomorrow without a mutation fails the self-test
rather than joining the suite unexamined.

**2. A check whose subject has vanished FAILS LOUDLY.** A file that is gone, a
repository that is missing, an anchor that matches nothing: all three are red,
with a message naming what disappeared. Silent success on a missing subject is
how the estate got here. The one exception is a repository `estate.json`
records as having no public remote, and even then the run reports PARTIAL and
names it, never clean.

## The checks

**C1, pin currency** (`gates/c1-pin-currency.py`). For every repository whose
`go.mod` requires `github.com/TAIPANBOX/agent-stack-go`, compares the pin with
the module's newest tag. Any lag fails; the finding says whether it is a minor
(a different contract, since the module is pre-1.0) or a patch (the same
contract, missing fixes). A pin ahead of every tag fails too, as does a
`replace` directive, which makes the pin unenforceable. A fresh release turns
this red for every consumer on the day it is cut, deliberately: that is the
day the estate is most drifted, and a grace period would report green during
the exact window the check exists to describe.

**C2, vendored schema equality** (`gates/c2-vendored-schemas.py`). The eight
vendored copies of agent-passport's three canonical schemas, across
agent-stack-go, genaryx, engram and verdryx, compared BYTE for byte with a
unified diff of the first difference. Byte-exact on purpose: two JSON
documents that differ only in whitespace or key order are the same schema to a
validator and a different one to the person who opens the file to see what the
canonical says.

**C3, mirrored constants** (`gates/c3-mirrored-constants.py`). verdryx's three
hand-copied mirrors of tokenfuse constants: the Breaker block-decision wire
strings (compared as sets), the default price book (per model and on the
fallback), and the trace Parquet column names verdryx reads (containment: it
reads five of sixteen). It PREFERS tokenfuse's published
`contracts/tokenfuse-constants.json` when that artifact is present and parses
the Rust when it is not, and it says which mode it used in every run, because
a comparison whose reader does not know what was compared is one somebody will
quote wrongly later.

**C4, event registry versus actual producers**
(`gates/c4-event-registry.py`). agent-passport `SPEC.md` section 6.2 is the
registry: source to event types. Both directions. Forward: every source it
lists has a real event-writing code path and every type string it lists
appears at an emit site. Reverse, and more valuable: any type string emitted
by any repository whose source the registry does not carry, or which is
attributed to the wrong source. Anchored on the emit call sites in Rust, Go
and Python, never on strings that look like event names, and a repository
whose shape defeats the parser is reported as a hole rather than skipped.

**C5, deployment parity** (`gates/c5-deployment-parity.py`). stack-up,
stack-single and stack-k8s compared on four things: which governance routines
each installs, the `HERALDYX_MIN_SEVERITY` default, the fixed local port map,
and which components each brings up. Differences are not automatically
failures, because several are deliberate, so this one fails on any divergence
that `expectations/deployment-parity.json` does not record with a reason and a
date. It fails the other way too: an expectation recorded for a divergence
that no longer exists is red, so the file cannot become a graveyard of stale
allowances.

**C6, cross-language chain vectors** (`gates/c6-chain-vectors.py`).
`agent-stack-go/event/testdata/chain-vectors.json` pins the RFC 8785
canonicalization and the SPEC 6.5 chain hashes. Three implementations retype
those values as literals in their own suites: Rust in tokenfuse, Python in
engram and in verdryx. A change to the Go canonicalization would not fail any
of them today. This compares every copy with the file.

**C7, the agent_id rule copied into code** (`gates/c7-rule-in-code.py`). C2
holds vendored schema FILES byte-identical and cannot see a rule that was read
out of a schema once and retyped as a constant. The estate has four of those
for one rule, SPEC 3.1's `agent://<trust-domain>/<name>` grammar and its
255-byte cap: `agent-stack-go/passport/passport.go`, which six repositories
import by tag, the Python copies in engram and verdryx, and the Rust one in
tokenfuse. A drifted file shows up in a diff; a drifted constant compiles,
passes its own suite, and is visible only to somebody holding both repositories
open. Each extractor anchors on a NAME and captures whatever pattern sits
beside it, so a rename breaks loudly rather than quietly finding nothing. Three
anchor on a constant; tokenfuse compiles its regex inside a function, so that
one anchors on the function and refuses to cross another `fn`.

## Running it

Locally, against the sibling checkouts in the parent directory:

```sh
./run-gates.py                      # every gate, summarised
./gates/c4-event-registry.py        # or one on its own
./selftest.py                       # prove the gates can fail
./scripts/no-long-dashes.sh --prove
```

Three sources, and every run prints which one it used:

```sh
./run-gates.py                          # the working trees, as they are now
./run-gates.py --mode ref --ref origin/main   # the estate as published
./run-gates.py --mode clone             # fresh shallow clones, what CI does
```

`--mode ref` is the one to reach for while other people are editing: a working
tree mid-edit will report drift that is somebody's uncommitted fix, and
`origin/main` answers the question the nightly run answers.

Exit codes: `0` clean and complete, `1` the estate drifted, `2` a repository
that should have been reachable was not, `3` clean but some repository with no
public remote went unread. CI treats 3 as success with a notice and fails on
everything else.

## What is deliberately NOT covered

Written down rather than left implied, because an unstated gap reads as a
covered one.

- **Repositories with no public remote.** taipan is private and bank-in-a-box
  deliberately has no remote at all. In CI they are reported as unmeasured and
  the run ends PARTIAL. `taipan demo` writes envelopes attributed to other
  planes, so its attribution is checked in local runs only.
- **`go.sum`, `replace` targets and vendored Go code.** C1 reads the version
  in `go.mod`. It reports the presence of a `replace` as a failure but does
  not follow it.
- **Event types built at runtime.** C4 anchors on literal strings at emit
  sites. A type assembled from a variable or a format string would be missed,
  and the anchor would still match, so nothing would complain. None exists in
  the estate today.
- **The severity column of SPEC 6.2.** The registry gives a typical severity
  per type in parentheses and tokenfuse fixes severity per type in code. Those
  are a fourth mirror and nothing compares them.
- **trailryx and catalog.** In `estate.json` so that a future check has a
  place to start, read by nothing today.
- **Whether a claim is TRUE.** Every check here compares two statements the
  estate makes about itself. Two documents that agree can still both be wrong,
  and no script can tell.
- **Anything an operator supplies at install time.** C5 reads the defaults in
  the source. What a given box is running is not a property of a repository.
- **The estate's OWN gates.** Nothing here checks that the per-repo gates
  still run or still mean what they say. That belongs to each repository.
- **A coverage statement.** `estate.json` lists the estate, and there is no
  machine-checked link between "repositories that exist" and "repositories any
  check reads". A repository could join the estate and be covered by nothing,
  and only a person reading this section would notice.

## The gaps a check cannot hold

Everything above is what a script decides. [`GAPS.md`](GAPS.md) is the standing
register of what it cannot: the estate's open security findings, the seams no
gate reaches yet, what agent monitoring can and cannot see, and the invariants
every repository holds by prose alone.

It is a record rather than a source of truth. Nothing in it is authoritative
about anything a command can decide, and its section 1 is a dated reading of a
`run-gates.py` run rather than a second copy of one. Every item carries how to
re-check it, because in this estate a `file:line` citation goes stale in days:
on the day the register was opened, all three citations it tried to follow from
a four-day-old audit had moved, and all three findings had been fixed.

## Known uncovered mirrors

Copies that exist and are not compared, because they could not be anchored
exactly and a guess is worse than an honest gap:

- **tokenfuse's event-type severities against 6.2's parenthesised ones**, as
  above.
- **heraldyx's `internal/render` catalogue**, which maps an event type to what
  it MEANS for an operator. Four of seventeen entries were found wrong in an
  audit. Nothing structural can check that an explanation is true.
- **The stack sentence and the component count** that several repositories
  repeat in prose. Anchoring on English is how a gate learns to cry wolf.

## A red badge here

means the estate drifted, not that this repository is broken. That is the
whole design: every check compares two other repositories, and this one has no
opinion of its own to be wrong about. When it is red, open the finding, and it
will name both sides and the file to open.

Several checks are red today. That is correct, and working around any of them
by weakening the check would be the one change this repository cannot survive.
