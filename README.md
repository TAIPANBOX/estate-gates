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

**C8, the registry reaches the record** (`gates/c8-registry-reaches-the-record.py`).
C4 holds SPEC 6.2 against the producers and says nothing about what becomes of
an event afterwards. trailryx is the record plane, and a type its ingest door
does not know is refused as `UnknownType` and counted. That refusal is correct
behaviour, and it is also what an omission looks like: "we decided this does
not belong in the record" and "nobody got to it" produce the same refusal, the
same counter and the same silence. trailryx already writes its decisions down,
in a doc-comment passage naming the types it refuses on purpose, so this check
asks only that every registered type appears on one of the two lists, the
mapping arms or the refused names. It never requires a mapping: the record
vocabulary is deliberately narrower than the bus, and forcing a record type per
registered type would be the wrong direction. Writing it found `policy_updated`,
wardryx's admin type at severity `high`, on neither list, which meant the record
plane was silently dropping the event that says an operator changed the policy
rules.


**C9, a git command aimed elsewhere clears the hook's environment**
(`gates/c9-foreign-git-in-hooks.py`). git runs a hook with `GIT_DIR` set to the
repository being pushed, and `git -C <somewhere else>` changes the working
directory without clearing it, so the command reads the other repository's
working tree against this one's index and object database. Found in trailryx on
2026-08-26: a check asking whether the local advisory database had untracked
files answered nothing from a terminal and all 1221 of its entries from the
pre-push hook, and refused the push. Three sessions retried instead of looking
at the environment, because the failure only exists in a context nobody debugs
from. The quieter shape is worse than the one that was found: `show <ref>:<path>`
under the wrong object database resolves the ref in the wrong repository, and
where both hold a file at that path it succeeds and returns the wrong content,
so a check comparing a vendored copy against its original compares the copy
against itself. The single rule that keeps this honest is that the target must
sit before the subcommand, where git requires it, which is what keeps
`git archive HEAD | tar -x -C "$dir"` out of the answer: five repositories write
that line, and a check matching `git` and `-C` anywhere would have reported all
five and been deleted by whoever read the first finding.


**C10, the RFC 8693 mapping produces one chain in every language**
(`gates/c10-delegation-mapping.py`). agent-passport SPEC 5.3 says how an RFC
8693 `act` claim becomes an `on_behalf_of` chain, and it is the one place in
this estate where a mistake produces something that VERIFIES PERFECTLY and
asserts the opposite of what happened: a signature is over the claims and says
nothing about how a reader turned them into a list. Two mistakes are available
and both were made on 2026-08-26, in the hour the mapping was first written.
The direction: the RFC nests `act` current-first, SPEC 5 orders the chain
root-first, and reversing it wrongly records that the root delegated to nobody.
The head: the RFC keeps the subject OUT of `act` and SPEC 5 puts the root INTO
the chain, so the mapping is `[sub] + reverse(act)`, and missing that writes the
chain with the human missing from it. Two implementations exist and neither can
see the other, each holding its expected chain as a literal in its own suite, so
changing one leaves the other passing against the old answer. The gate reads the
ASSERTION rather than the test body, which is the correction its own self-test
forced: taking the last three principals found the same three whatever the
assertion said, because a body also names the principals that BUILD the token,
and the gate could not see the exact failure it exists for.

**C13, the delegation depth cap counts one thing**
(`gates/c13-delegation-cap.py`). SPEC 5.1 reads "Maximum chain depth is 32
entries" and SPEC 5 calls the members of `on_behalf_of` entries, so the bound
belongs to the assembled chain. SPEC 5.3's mapping is `[sub] + reverse(act)`,
so a producer building that chain out of an RFC 8693 token bounds two
quantities one apart, and one sentence cannot tell it which one it meant.

Measured 2026-08-27 with agent-conform against a real emitted line: both
producers in the estate had bounded the ACTORS at 32 and then prepended the
subject, while every consumer bounded the CHAIN at 32. A token carrying 32
actors verified at the door and every record it produced was quarantined with
`maxItems: got 33, want 32`. Every number read 32, every repository was
internally consistent, and every suite was green: the disagreement was in the
UNIT, which is precisely what no repository can see about another.

Three sides, all discovered. The SPEC's sentence, parsed for the number and for
the unit word, so a reworded sentence is a red rather than a silent
re-reading. Every JSON Schema anywhere in the estate that DECLARES
`on_behalf_of`, found by searching each repository for the member, so a
vendored copy is a subject the day it lands and one that bounds nothing is a
consumer accepting what the SPEC forbids. And every cap constant under a
`chain` or `delegation` path, where an entries cap must equal the SPEC's number
and an actors cap must equal it minus one AND be derived from the entries cap
rather than retyped.

The finding to read first is none of those three. A file that maps an `act`
claim into a chain must state BOTH numbers, and that check does not depend on
finding a cap at all, so a constant renamed out of the anchor cannot switch it
off. Run against the estate as it stood on the morning of 2026-08-27 it names
`agent-stack-go/delegation/chain.go` and `tokenfuse/crates/delegation/src/lib.rs`,
which is the defect, from the only place in the estate that could have seen it.

**C16, a launcher's environment reaches a reader**
(`gates/c16-launcher-env-has-a-reader.py`). C5 compares the three launchers
against each other, so it has no opinion about whether the thing all three
agree on is wired to anything. This asks the other question, between a launcher
and a binary: every environment variable a launcher hands to a process must be
one some repository declares reading.

Two live instances the day it was written, both the same shape.
`stack-single/compose.yaml` passed `WARDRYX_DSN`; wardryx reads `WARDRYX_DB`
and has never read the other name, so the launcher generated a correct DSN,
declared `depends_on: policy-db` with `condition: service_healthy`, waited for
that database to come up, and handed the value over under a name the process
ignores. The database was provisioned, waited on and never used, which left
policy and approvals in memory: a restart dropped every console-written policy
and unfroze the fleet while the console still showed it stopped. And `stack-k8s`
sets `TOKENFUSE_CLOUD_EVENTS_PATH` into a container by `configMapKeyRef`; that
name appears nowhere in tokenfuse, whose cloud reads
`TOKENFUSE_CLOUD_REPLAY_EVENTS`, which no launcher sets at all.

A key with no reader is the quiet kind of wrong. Nothing is misspelled, nothing
errors, the value is correct, the dependency is healthy and the service starts
and answers. It is a wire that was never connected while every signal around it
says the opposite. Neither instance is visible from inside a repository: the
launcher's gates cannot read the binary and the binary's gates cannot read the
launcher.

Both sides come from the repositories. The answer is every name under an `env`
block in any `components.json`, and those declarations are not this suite's
word for it: each declaring repository proves its own manifest against its own
source in its own CI, per C15's argument about why that division is structural.
The subjects are what the launchers DELIVER, by four forms read off the
launchers themselves, with comments stripped first so that prose about a
variable, including the comment recording the `WARDRYX_DSN` fix, is not a
delivery. `install.sh` holds shell variables like `WARDRYX_ADMIN_SECRET` that
reach no process, and flagging those would bury the real finding.

The subject is delivery to ONE service: a container's own `env:` entry, a
compose service's own `environment:` mapping, a shell command prefix. A shared
ConfigMap's keys are not subjects. The first version counted them and reported
seven findings, three of them wrong for the same reason. The clearest was
`TOKENFUSE_CLOUD_EVENTS_PATH`, which is a KEY whose value reaches the container
under a different NAME (`TOKENFUSE_EVENTS_PATH`, which tokenfuse declares and
reads); `IDRYX_URL` is the same shape, and stack-k8s interpolates
`TRAILRYX_TRUST_DOMAIN` into an argument in a CronJob it writes itself, which
trailryx's own suite deliberately keeps out of its manifest and says so. Three
repositories were right and the check was wrong. Narrowing cost coverage on
purpose: three false findings buy a check somebody still reads at the tenth run.
That is also the shape the original defect had, since `WARDRYX_DSN` was in the
wardryx service's own `environment:` block.

Its remaining limit: a variable delivered by a form not listed is invisible
here and nothing would say so. The mitigation is that the forms are read from
the launchers rather than imagined.

**C17, a tag-only workflow is exercised by a pull request first**
(`gates/c17-tag-workflow-pr-guard.py`). A workflow gated on `push: tags: v*`
runs for the first time, on every commit that ever reached it, on the day
somebody cuts a release. tokenfuse's `binaries` job failed on both Linux
runners the first time `v0.4.2` exercised its musl leg, on a step that had
been wrong since it was written and had simply never run before that tag. The
fix, TAIPANBOX/tokenfuse#251, is two things done together: a `pull_request`
trigger scoped to the workflow's own path, so an edit to the file is what
exercises it, and every job that publishes guarded off that event, so the
same pull request does not also push an image or cut a release. Subjects are
found, never listed: every file under `.github/workflows/` in every
repository `estate.json` names whose `on.push.tags` matches `v*`. A survey by
hand found ten repositories with the shape and no escape hatch at all; this
gate's own discovery finds twelve, naming engram and terraform-provider-taipan
as well, both of which publish (to PyPI and to the Terraform Registry) on a
bare tag push with no `pull_request` trigger anywhere. Four equivalent guard
expressions are accepted (`github.event_name != 'pull_request'`,
`startsWith(github.ref, 'refs/tags/')`, `github.event_name == 'push'`,
`github.ref_type == 'tag'`), because the estate's own clean files use more
than one of them. What counts as publishing is a fixed, named list:
`docker/build-push-action` with `push` or `push-by-digest` true, `docker
buildx imagetools create`, `softprops/action-gh-release`,
`actions/upload-release-asset`, `gh release`, `docker push`, `cosign`,
`crane`, `oras`. A marker outside that list, or a guard that is logically
equivalent but spelled differently, is invisible to it, which is stated here
rather than silently missed.

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
- ~~**Event types built at runtime.**~~ **Closed 2026-08-09.** This said a
  type assembled from a variable would be missed with nothing complaining, and
  that no such producer existed. Both halves were wrong within the day: scopyx
  names its types as constants and passes the variable at the emit site, so C4
  read it as a producer with no types and reported the run clean. The Go parsers
  now return what they could not resolve and the extractor refuses on it, so
  that shape is a loud hole. A type built from a format string is still beyond
  the parser, but it is now a REFUSAL rather than a silence.
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
- **Whether a component starts BY DEFAULT.** C5's `services` family answers
  "does this deployment bring this component up", and both heraldyx and scopyx
  are present in all three while being opt-in in two of them: excluded from
  stack-k8s's `apply -k` set, behind a compose profile in stack-single, and on
  by default only in the stack-up sandbox. C5 reports them as agreeing, which is
  true of the question it asks and not of the question a reader may think it
  asked. Noticed 2026-08-09 while adding scopyx; not modelled, because a family
  for it would have to distinguish "opt-in for a security reason" from "not
  wired up yet", and those look identical from the outside.
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


**C11, a proved chain was proved by something**
(`gates/c11-proven-means-verified.py`). wardryx decides on `chain_proven`, and
its own comment states the trust boundary plainly: "a caller that lies about
this is believed. That is not a weakness of this field, it is where the boundary
is." That is correct, and it is exactly why the check belongs on this side of
the boundary. The PDP cannot tell a verified `true` from an asserted one, and
nobody can from inside wardryx: it is visible only to something holding wardryx
and every producer open at once.

The failure it names is the one the 2026-08-25 identity plan called A5, and the
dangerous half is not the one the plan led with. A chain wrongly marked unproven
makes a policy fire that should not have, which somebody notices. A chain
wrongly marked proved makes `deny_if_chain_unproven` stay silent, and an estate
where that rule never fires looks exactly like an estate where every chain is
proved.

So every non-test file that sets `chain_proven` true must CALL a verifier. A
call and not an import: `use tokenfuse_delegation::verify_delegation;` at the
top of a file that never calls it is what a refactor leaves behind, and counting
it would let this pass on the wreckage. It reads text rather than data flow, so
it sees a literal `true` and not a variable that happens to be one. That is the
shape a rubber stamp actually takes, and the limit is written in the script
rather than left to be discovered.