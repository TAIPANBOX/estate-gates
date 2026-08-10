# TAIPANBOX estate: the gap register

**What this file is.** The standing record of everything in the estate that is
unfinished, ungated, or known-broken: security, the seams between services,
agent monitoring, and functionality that exists on paper and not in the code.
It is meant to be re-read and refreshed, not written once.

**Opened:** 2026-08-09. Moved here from `~/Development` the same day
`@yurii 2026-08-09`, "Перенеси в estate-gates".

**Why it lives in this repository, whose `CLAUDE.md` forbids status.** That
rule is about `CLAUDE.md` itself, and it is right: an instruction file that
carries status is trusted on the strength of the half that is still correct.
This file is the other thing, the one that rule implies has to exist somewhere.
The estate's gaps are cross-repository by nature, and this is the only
repository allowed to know about more than one repository at once. It sits
beside `expectations/deployment-parity.json`, which is likewise a record rather
than configuration.

**What keeps it from becoming the stale document that rule warns about** is
section 0.2, and specifically that nothing here is the authority on anything a
command can decide. Section 1 is a reading of `run-gates.py` output, not a
second copy of it.

**Section 10 is the exception to the whole shape of this file.** Everything
else records a gap; that section records estate-wide decisions about what gets
built, so that a decision does not survive only in the session that made it.

---

## 0. How to use this file

### 0.1 Provenance

- Unmarked is `@claude`: my reading or judgement. Re-check before acting.
- `@measured <how> <date>`: established by a run, with a reproducible command.
- `@yurii <date>`: Yurii's decision, quoted.

### 0.2 Four rules this file lives by

**1. Every item says how to re-check it, not only where it was found.**
This is not style. On 2026-08-09 I tried to re-verify the three top priorities
from the 2026-08-05 audit using its own `file:line` citations, and **all three
paths had moved**: `verdryx/costper.py` is now `verdryx/verdryx/costper.py`,
idryx's dashboard moved from `internal/report` to `internal/server`, and
tokenfuse's settle path was restructured. A register that cites only a line
number is stale within days in this estate. Cite the **property** and the
command that decides it.

**2. A refresh updates numbers and closes items with evidence. It never
rewrites a status sentence into a healthier one.** If an item's claim stops
being true, it is closed with the evidence that closed it, in section 8. It is
not quietly softened.

**3. Closed items stay, struck through, with their evidence.** A register that
deletes what it closed loses the record of what was ever checked, and the next
audit re-discovers the same thing.

**4. "Not checked" is a state this file reports, not a silence.** Section 9
exists so the shape of what nobody looked at is visible.

### 0.3 The one command that refreshes half of this file

```bash
cd ~/Development/estate-gates && ./run-gates.py --mode ref --ref origin/main
```

Six cross-repo checks. Section 1 is entirely its output. It takes about two
seconds and it is the cheapest thing in this document.

---

## 1. Live cross-repo drift

**The gate run is the authority for this section and this file is not.** What
follows is a dated reading of one run, kept because the interpretation is worth
writing down and the raw finding is not: the suite says two schema copies differ
by a few bytes, and the paragraph below says which bytes and why they matter.
If this section and a fresh run disagree, the run is right and this section is
overdue a refresh.

@measured `./run-gates.py --mode ref --ref origin/main`, 2026-08-10, after the
v0.3 work: **six of seven clean, C1 drifted, and every subject was measured.**
The suite has grown a gate since the reading below was written.

**C1's red is a release in progress rather than a defect, and it is exactly what
that check is for.** agent-stack-go cut `v0.7.0` today, and C1 refuses any lag
by design: "the day after a release is exactly when the estate is most drifted",
in its own words. heraldyx and idryx are on it because they needed it;
`mockryx`, `qryx`, `scopyx`, `wardryx` and `terraform-provider-taipan` have a
one-line PR open each and are behind until those merge.

Read that red as a countdown rather than a finding. If it is still red once
those five merge, it is a finding again.

Earlier the same day, after estate-gates#14 and before the tag: all 7 clean.

**Earlier the same day C5 was red, and what it found is worth keeping**, because
it is the difference between a gate that cannot see and an estate that
disagrees. `stack-single` had grown a component called `scopyx-browser`, and C5
had no mapping for that name in its own `SERVICE_KIND`, so it refused to compare
that component rather than defaulting it, said so, and named the file to edit.
That is invariant 2 working: a subject a check cannot read is a red naming what
it could not read, never a skip.

The name turned out to be the same plane in a second compose profile, which
`stack-single/compose.yaml` says of itself: `egress` and `egress-browser` are
mutually exclusive and both bind the network alias `scopyx`. So it is one
component with two backends, and estate-gates#14 teaches C5 that one name.
Proven not to be a widening by planting `scopyx-experimental` and watching C5 go
red about it, then clean again with the probe removed.

Everything else C5 reads is green, including the routine counts that section
G1.3 is about (stack-k8s 4, stack-single 0, stack-up 5).

The previous reading, kept because its interpretation is still the useful part:

@measured `./run-gates.py --mode ref --ref origin/main`, 2026-08-09, second run
of the day: **all 6 gates clean, and every subject was measured.**

The first run of that day found three gates drifted. All four findings across
C1, C2 and C5 were closed the same day and are in section 8 with the evidence.
This section keeps only what is still open.

**The mode is part of that claim.** CI runs `--mode clone`, where `taipan` is
private and `bank-in-a-box` has no remote, so C4 reports **partial, something
went unmeasured** rather than clean. Both readings are true of their own mode.
Anybody comparing this section against a badge should expect that one
difference and no other.

**A clean suite is not a clean estate, and this is the sentence most likely to
be quoted wrongly.** The README's own list of what C1 to C6 deliberately do not
cover is longer than what they do, and sections 2 to 6 below are almost entirely
things no gate here can see. Six green ticks mean the six comparisons agree.

### G1.3 Two deployments do not run the governance routines, and C5 is green about it

This is the shape most worth understanding in this file, because C5 is clean and
the gap is open at the same time, and both are correct.

`stack-single` installs **no governance routine of any kind**: no cron, no
timer, no supervisor, no periodic compose service. Not `focus-export`, not
`idryx-detect`, not `qryx-trend`, not `verdryx-drift`. `stack-k8s` runs four and
lacks `focus-export`, so a Kubernetes install produces no FOCUS export at all.

Both are **recorded** in `expectations/deployment-parity.json`, both explicitly
as gaps rather than decisions, and invariant 7 makes a recorded divergence green.
C5's job is that a divergence is either explained or red, not that it is absent.
A green C5 therefore means nobody has silently changed what the three
deployments do; it does not mean they agree.

**Two corrections to the first version of this entry, both measured 2026-08-09.**

It said the single-box case is "the exact failure mode the silent-zero rule is
about". It is not silent. `stack-single/install.sh` says so twice, once in its
header comment under "What this box does NOT run, so you can compare before
installing rather than after", and again in the banner the operator reads when
the install finishes. A disclosed gap is still a gap and is a different thing
from a box that lies about itself.

And `stack-k8s`'s missing `focus-export` is not an oversight anybody forgot.
`GOTCHAS.md` and the manifest comment record why it is harder than the other
four: `focus-export` needs the trace directory, and the claim that backs the
other CronJobs cannot back it the same way. That is a design problem with a
recorded reason, not a line somebody failed to write.

**Closes when:** the routines run in both, or somebody decides the absence is
correct and the expectation entries say `decision` instead of `gap`. The second
is a claim about what the product is and needs the user, per this repository's
own escalate list.
**Re-check:** the C5 section of the gate run, which prints every recorded
divergence with its reason.

### G1.5 The pin table in agent-stack-go's CLAUDE.md is a fourth copy, and all six rows are wrong

@measured 2026-08-09, after the six consumers moved to `v0.6.0`:
`agent-stack-go/CLAUDE.md` carries a "Repo | Pins" table under **Blast radius**
listing `idryx v0.5.1`, `wardryx v0.4.0`, `mockryx v0.4.0`, `qryx v0.4.0`,
`heraldyx v0.4.0` and `terraform-provider-taipan v0.1.0`. Every one of the six
is now `v0.6.0`.

Five rows went stale today. The sixth was already wrong before anything moved:
C1 measured `terraform-provider-taipan` at `v0.5.1` while that table said
`v0.1.0`, so it had drifted at least one bump earlier and nothing noticed.

The table is a **fourth copy of what C1 measures**, sitting in a file whose own
first paragraph says it holds process and invariants only and no status. Its
own caption asks the reader to keep it beside two other lists, which is the
estate's most-repeated defect written down as an instruction.

**Closes when:** the table is deleted and its sentence points at C1, or a gate
compares it against the `go.mod` files it describes. Deleting is the better
answer: the reason C1 exists is that hand-maintained copies of a measurable fact
do not survive.
**Re-check:** compare that table against `grep TAIPANBOX/agent-stack-go */go.mod`.
**Gated by:** nothing. C1 reads `go.mod` files and has no opinion about prose in
a sibling's instruction file.

---

## 2. Agent monitoring: what we can and cannot see

This section is new on 2026-08-09 and is the largest single body of gaps. It
exists because the question "can an agent bypass us" had never been written
down with an answer.

### G2.1 Taint is decided on a name the caller chose, not on the act

@measured `tokenfuse/crates/core/src/taint.rs:122-135` and
`crates/gateway/src/firewall.rs:27-34`, 2026-08-09: `labels_for_tools` maps
**tool names** to labels through a `HashMap`; an unmapped name becomes
`unclassified`.

So "has this run touched an untrusted source" is answered by a string the agent
reported, and the network act behind it is invisible. We do not know which URL
was fetched, whether it left permitted domains, or what came back.

This is TokenFuse invariant 15's own complaint ("identity comes from the
credential and never from a header") one layer up, applied to tools instead of
identity.

**Closes when:** a fetch passes through an enforcement point that labels from
the observed act. See `browse-plane-plan.md`.
**Re-check:** open `firewall.rs` and ask what supplies the `web` label.

### G2.2 `allow_domains` has no runtime enforcement point anywhere

@measured `wardryx/internal/policy/policy.go:44-52`, 2026-08-09. The field's own
doc comment states it constrains only what a caller declares, and that runtime
tool-egress enforcement "is an enforcement point's job, not this field's".

No such enforcement point exists in the estate. The one network control the
policy language offers is, today, an honour system.

**Closes when:** something enforces it per fetch and per subresource.
**Re-check:** grep the estate for a consumer of `AllowDomains` that acts on it
rather than reporting it.

### G2.3 The NetworkPolicy protects our planes and does not confine agents

@measured `stack-k8s/manifests/30-network-policy.yaml`, 2026-08-09: the
`agent-stack` namespace contains `plane: money|policy|identity|console`,
`app: wardryx`, `app: policy-db`. **There is no agent workload in it.**

Default-deny egress is real and it governs the stack. The customer's agents run
outside the namespace, on their own machines, unconfined by it. The manifest's
own headline, "the governance story told at the network layer", is easy to read
as confining agents. It does not.

**Closes when:** either agent workloads are brought into a namespace with a
policy written for them, or the README says plainly which side of the line the
policy sits on.

### G2.4 A general egress sensor exists and nothing asks it the right question

@measured `Idryx/internal/ebpfcapture/capture_linux.go`, `environ.go`,
`cmd/idryx/main.go:1160-1200`, 2026-08-09. This is better than expected and is
listed here as an opportunity, not a defect:

- it captures **every** outbound connection (pid, dport, IP), discarding only
  loopback that is not a local model port;
- it reads `AGENT_PASSPORT_ID` from the process environment, so a flow is
  attributed to an agent;
- `idryx ebpf-capture` writes it in exactly the shape
  `internal/ingest/egress.go` already parses, so it plugs into the same
  `detect/bom/serve/load/remediate` pipeline as every other source;
- detectors already exist: `shadow_mcp`, `agent_shadow_tool`, `undeclared_llm`,
  `claimed_agent_drift`, `mcp_drift`.

What is missing is one detector. **Nothing asks "did this agent reach a host it
was never routed through an enforcement point to reach".** That is a join
between the eBPF egress log and an enforcement point's event journal, and both
datasets already exist in compatible shapes.

**Closes when:** an `unrouted_egress` detector exists in idryx and its finding
reaches the shared bus. The second half depends on G4.1.

### G2.4 is HALF closed, and the sentence above is wrong about the datasets

**The detector exists.** idryx#43, merged 2026-08-10. **Its finding does not
reach the bus**, and that half is now blocked on something this register had not
named. Both halves below are `@measured` on the same run.

**The join this item describes cannot be built, and that is the more useful
result than the detector.** "Both datasets already exist in compatible shapes"
was my sentence and it was wrong three ways:

- the sensor reports ADDRESSES and substitutes a hostname for exactly three
  hosts, resolved once at startup (`Idryx/internal/ebpfcapture/capture_linux.go`,
  `knownLLMHosts`); scopyx's journal records an ORIGIN, `https://docs.example`,
  and deliberately never more of the URL. They meet on three hosts out of the
  internet;
- closing that gap by resolving names inside a detector puts DNS in the
  detection path, which is idryx invariant 1 gone;
- and in the deployment scopyx ships, the governed side is invisible to the
  sensor anyway. It is an MCP server, its default bind is `127.0.0.1:4300`, and
  the sensor discards loopback that is not a local model port.

A detector written as this item describes would have compiled, passed its tests
and found nothing on a real run. That is the shape section 6's class 2 is about,
arriving through a register entry rather than through code.

**What was built instead is the inversion**, which needs no hostnames: a
governed fetch is performed by the enforcement point's own process, on all three
of its backends, so a flow the sensor attributed to a governed agent, reaching a
PUBLIC address, could not have been governed. The journal supplies the
precondition (this agent is in scope) rather than the comparison. Private,
loopback and carrier-NAT destinations are not judged, because scopyx's own
address rules refuse those ranges, and model APIs are left to the shadow-AI
detectors; both are counted in the finding rather than dropped.

**Why the second half did not close, and it is not G4.1's fault.** G4.1 closed
on 2026-08-09 and idryx does emit. The blocker is narrower and was not visible
until a detector needed it: **the subject of this detector is a claim by
construction.** `AGENT_PASSPORT_ID` is the only way the sensor can name an
agent, so the finding is about `claimed:agent://...`, and the envelope has one
subject field with no way to qualify it. Writing the claim into `agent_id` would
deliver a self-declaration to every conforming consumer as an established fact,
which agent-passport SPEC 3.3 forbids, and no `data` key repairs it because 6.1
obliges a consumer to ignore keys it does not know. See G4.5.

`@measured` 2026-08-10,
`IDRYX_EVENTS=... IDRYX_TRUST_DOMAIN=acme.example idryx detect --load scopyx:testdata/scopyx.ndjson --load egress:testdata/ebpf_claimed.json`:
four findings reached the bus with correct subjects, and idryx reported
`3 were about a self-declared (claimed:) identity the envelope cannot carry`.

~~**Closes when:** G4.5 does.~~ **CLOSED 2026-08-10**, the same day it was
opened as half closed. G4.5 closed, so this did.

`@measured` on the same command, after idryx#44: the journal carries three
`v0.3` events whose subject is `claimed:agent://...`, including both
`unrouted_egress` findings, and idryx reports `3 were written about a
self-declared (claimed:) identity under schema v0.3` where it had reported the
same three as unwritable. Established findings still stamp `v0.2` with a bare
`agent://` subject, which is the half a reader would not notice if it broke.

**Re-check:** the command above. A nonzero SKIPPED-claimed count would be this
gap returning; a nonzero WRITTEN-claimed count is it working.

### G2.5 Four limits on agent monitoring that no amount of work removes

Listed so they are never sold as closable:

1. **Provider-side web search is enforceable by nobody.** When an agent uses
   Anthropic's or OpenAI's built-in search, the fetch happens on the provider's
   infrastructure. TokenFuse sees the `tool_use` in the response, so it can
   apply a taint label; it cannot apply a domain policy. This is a boundary.
2. **The eBPF sensor is Linux-only**, and needs root or CAP_BPF plus a
   BTF-enabled kernel. A developer laptop on macOS is not covered.
3. **`AGENT_PASSPORT_ID` attribution is self-declared.** SPEC §3.3 says so
   explicitly. An agent that wants to hide unsets it: the flow is still seen,
   the attribution is not. Acceptable for detection, never for authorisation.
4. **An agent with code execution can always open a socket.** Enforcement
   points constrain routed traffic. Only the network layer constrains a
   process, and only where we own the deployment.

---

## 3. Security

**Every item here was re-verified against the code on 2026-08-09.** Seven were
carried from the 2026-08-05 audit unchecked; all seven have now been opened.
**Six are closed** and are in section 8 with the evidence. What remains is one
constraint that is not a defect, and one correction to a finding that was
wrong.

### G3.4 trailryx: the SQL read surface never filters a row

**Not a defect, and listed so it is not mistaken for one.** trailryx invariant
27 states the surface admits or refuses a connection and never filters a row,
with the deployment model being one server per scope: two tenants means two
servers.

The risk is documentation drift rather than code. Its own unit tests, showing
two scopes refusing each other's principals, read as tenant isolation to
anybody who has not seen invariant 27, and teach the opposite conclusion.

**Closes when:** nothing. It stays true or it is replaced, never quietly. The
day row filtering is added, that line must be replaced rather than deleted,
because the line a deployment was built on must not stop being true in silence.

### G3.5 was wrong about what ships, and the corrected finding is smaller and different

**The original claim, from 2026-08-05:** trailryx's federation
`PeerService::query` ignores the predicate and returns everything it holds to
anybody whose certificate chains to the CA, so possession of a certificate
equals full read.

**What is actually there**, @measured 2026-08-09. `transport::serve` is called
from the integration tests and from `bin/fed-probe`, which says of itself in
its own module documentation that it is "deliberately small and deliberately
not a service". It takes a fixed `Vec<Record>` and a `ServedProof` and answers
with them. **There is no production federation server in the workspace at
all**, so there is nothing shipped for a certificate holder to over-read: a
peer serves what its operator handed it, over mutual TLS, to a client whose
certificate carries a name the registry knows.

**The real gap, which is worth more than the one it replaces.** The proto says
the predicate is "sent as written; the far side decides what it can prove and
says so in the trailer". The only implementation of that far side ignores it,
no test asserts a predicate ever made an answer smaller, and the type calls
itself the answering half of a federation peer. So the reference implementation
teaches "return everything" to whoever writes the real one.

**Closed** by making the absence visible rather than by inventing filtering in
a harness: the doc comment says the predicate is not applied and why, the
binding is named so it reads as a decision, `VALIDATION.md`'s "Not yet
measured" carries it, and a test pins the current behaviour so it goes red the
day filtering arrives. See section 8.

**The lesson worth keeping** is about the first version of this entry rather
than about trailryx. It described a leak, and the severity came from reading
one function without asking who calls it. A finding that names a consequence
should name the caller that produces it.

## 4. The seams between services

### ~~G4.1 idryx emits nothing into the shared event envelope~~
**Closed 2026-08-10.** See section 8.
@measured `agent-passport/SPEC.md` §6.2, 2026-08-09: idryx's seven event types
are listed **RESERVED, not emitted**. Its detections leave by OTLP and by Slack.

Consequence, and it is why G2.4 is only half a solution: any detector idryx
gains, including an `unrouted_egress` one, produces a finding that reaches
neither heraldyx nor trailryx, because it never enters the bus they read.

**Closes when:** idryx has an event writer and SPEC 6.2's row stops saying
reserved.

**The vocabulary was measured 2026-08-10 and the reserved list is wrong in BOTH
directions**, which changes what this item is asking for. `@measured`
`grep -rhoE 'return "[a-z_]+"' Idryx/internal/detect/detectors/` against
`agent-passport/SPEC.md` §6.2:

- idryx ships **25 detectors**. 6.2 reserves **seven** names for it.
- **Two reserved names have no producer at all**: `excessive_privilege` and
  `blast_radius_change`. Nothing in the repository emits either, and
  `excessive_privilege` has three near neighbours that are not it
  (`excessive_agency`, `least_privilege`, `over_privileged_nhi`).
- **Twenty detectors have no reserved name**, including the ones the estate
  actually talks about: `shadow_mcp`, `agent_shadow_tool`, `undeclared_llm`,
  `claimed_agent_drift`, `unmanaged_egress`, `data_exfiltration`.
- **One name collides.** `mcp_drift` is a detector in idryx and a REGISTERED
  type under `tokenfuse` in 6.2. If idryx emitted it, C4's attribution check
  would be right to object, and a consumer would have two producers for one
  name with no way to tell which meant what.

So "stop saying reserved" was not an edit to a row, it was a decision about the
shape of the vocabulary. `@yurii 2026-08-10`, asked with both shapes measured
and costed: **"перший, один тип"**. The two shapes were:

- **one type**, `identity_finding`, with the detector name inside `data`. One
  row, one handler downstream, and the 25 names stay idryx's own vocabulary
  where they can change without a nine-repository edit.
- **many types**, one per detector. Every name is visible in the registry and
  every consumer can route on it, at the cost of 25 rows, 25 severities, 25
  entries in heraldyx's render catalogue, and a nine-repository edit each time
  idryx adds a detector.

His answer was the first, and it is built: idryx emits `identity_finding` with
the detector in `data.detector` (idryx#40), 6.2 registers it and the diagram
carries the arrow (agent-passport#33), and C4 reads idryx as an ordinary
producer rather than a reserved row.

`@claude`, the reasoning offered at the time: the first. The registry's own stated purpose is to tell a consumer
which events exist so it can act on them, and a consumer that must learn 25
names to handle identity findings will handle none of them. The second shape
also makes every new detector a spec change, which is the tax that stops
detectors being written. The collision decides itself under the first shape:
`mcp_drift` stays tokenfuse's, and idryx's detector of that name travels as
`data.detector` under `identity_finding`.

Recorded before building either, because a vocabulary is the one thing here
that cannot be changed quietly afterwards.

### ~~G4.2 `agent_id` is not validated against the `agent://` pattern by any emitter~~
**Closed 2026-08-09**, and it was the last of the three claims in it to go. See
section 8 for the evidence. Every emitter now checks, counts and warns; the
README example that produced a rejectable value has been rewritten to the
canonical form.

### G4.4 scopyx emits two types the registry does not carry, and C4 says clean

**The gate half is CLOSED as of 2026-08-09; the registry half is open and is
Yurii's.** C4 now carries a scopyx producer entry and, more importantly, its Go
parsers no longer DROP an identifier they cannot resolve: an event type written
as a variable is reported as a hole rather than as silence. C4 is now red about
scopyx, with both sides named, and that red is correct. It clears when SPEC 6.2
gains the row, which is an edit to agent-passport and routes through him.

The original finding, kept because the shape is the point:

**Found by registering scopyx** in `estate.json` on 2026-08-09. The run went to
seven gates clean, every subject measured, and that answer is wrong about this.

scopyx emits `web_fetch` and `web_blocked` (`internal/record/record.go`).
`agent-passport` SPEC 6.2 carries neither, and carries no `scopyx` source row
at all (`@measured` 2026-08-09, `grep -n 'scopyx\|web_fetch\|web_blocked'
agent-passport/SPEC.md` returns nothing). C4's reverse direction exists exactly
to catch that and did not fire.

**Why it did not fire, which is the part worth keeping.** C4 anchors on literal
strings at emit sites. scopyx names its types as constants and its emit site
passes the variable `kind`, so there is no literal at the call for C4 to read.
The anchor still matched the file, so nothing reported a hole either. This is
the limitation the README already states under "Event types built at runtime",
written there as hypothetical: it now has a real instance, and the instance
arrived the same day the repository joined.

**The shape.** A check that reports clean about a repository it structurally
cannot read is worse than one that skips it loudly, because the summary line
"every subject was measured" is then false and nobody has a reason to look.

**Re-check:**

```bash
grep -rn 'Type[A-Za-z]* *= *"' ~/Development/scopyx/internal/record/record.go
grep -c 'web_fetch' ~/Development/agent-passport/SPEC.md   # 0 means still open
```

**Closes when** SPEC 6.2 gains the scopyx row (scopyx's plan calls this WP9 and
routes it through the user, since the registry belongs to agent-passport), AND
C4 can see a type named as a constant rather than only one written at the call.
The second is the larger of the two: fixing only the registry would leave the
gate as blind as it is now, and the next producer to use a constant would be
missed in the same silence.

**The registry half is closed.** `@measured` 2026-08-10,
`grep -c 'web_fetch' ~/Development/agent-passport/SPEC.md` returns 3, and 6.2
carries `| scopyx | web_fetch (low) . web_blocked (high) |` beside a source row.
That is the half this item said returns nothing, and the re-check command above
now answers the other way. **The C4 half is untouched and is still the larger
one**, so this item stays open: nothing yet reads a type named as a constant.

### G4.5 A claimed subject has no way onto the bus, so a whole detector family never reaches it

Opened 2026-08-10, found by building G2.4's detector rather than by an audit.

agent-passport SPEC 3.3 requires a consumer to record an identity learned from
`AGENT_PASSPORT_ID` as CLAIMED, and an observer that reports it to make the
distinction visible. idryx does: the eBPF sensor records those identities under
a `claimed:` prefix, and they travel with it to Slack and to OTLP.

The shared envelope cannot carry that distinction. It has one subject field,
`agent_id`, and no way to say whether the subject was established or asserted.
So idryx holds those findings back rather than publishing a self-declaration as
a fact, which is the right call and leaves a real hole:

`@measured` 2026-08-10, `idryx detect --load egress:<capture with claimed ids>`
with the bus sink configured: every finding about a `claimed:` identity is
counted and not written. Today that is `unrouted_egress`, `claimed_agent_drift`,
`claimed_agent_unknown` and `shadow_ai`'s claimed-subject cases. None of them
reaches heraldyx or trailryx.

**This is NOT the whole eBPF family, and the difference matters.**
`unmanaged_egress` selects only `proc:` identities, which have no agent subject
under any envelope and correctly never travel. Only the claimed subset is in
play, and the fix would not change the `proc:` half.

**What it would take**, stated so the size is visible rather than discovered
later: a subject-basis field on the envelope (or a registered `data` key that
6.2 documents, so consumers are permitted to read it), plus heraldyx deciding
how it renders a claimed subject and trailryx deciding whether it files one
under that agent's history at all, and what its invariant 35 tenant check does
with a claimed foreign domain. That is a change every consumer makes together,
which is what SPEC 6.1 says about facts the envelope has no subject kind for.

**This is the user's, twice over:** it edits SPEC.md, and it decides how a claim
is recorded, which his standing rule of 2026-08-09 governs. Recorded here rather
than proposed, because a vocabulary decision is the one thing that cannot be
changed quietly afterwards.

~~**Closes when:** the envelope can say a subject was asserted rather than
established, and idryx writes claimed findings under it.~~ **CLOSED 2026-08-10**,
`@yurii 2026-08-10`, "зроби basis суб'єкта в конверті".

**The shape it closed in is not the one this entry proposed, and the difference
is the whole result.** This entry asked for "a subject-basis field on the
envelope (or a registered `data` key)". Both were built and rejected on paper
first, because §6.1 obliges a consumer to ignore fields it does not know: a
consumer that ignores `subject_basis: claimed` reads `agent_id`, finds a bare
id, and presents a self-declaration as established. That is SPEC 3.3's own MUST
NOT, reached by a consumer doing exactly what the spec told it to do.

Three measured consequences, in deployed code rather than in principle:

- **heraldyx would have mailed a kill link for the wrong agent.** Its mail
  carries `this agent <link> (freeze, kill)` where the link is
  `<console>/a/<agent_id>`. A process that wrote a victim's id into its own
  environment would have routed a woken operator to the innocent agent's card.
- **idryx would have laundered its own observation.** Its bus ingest treats a
  canonical `agent://` arriving from the bus as established, so the claim would
  have come back into its graph as an attested-grade identity.
- **Any new top-level field breaks the §6.5 chain.** `Canonicalize` marshals the
  typed struct, so a verifier older than the field drops it before hashing and
  reports a BREAK on an honest stream. Released `agent-conform` binaries would
  have called untampered files tampered.

**What was built instead** is the marker INSIDE the subject,
`claimed:agent://<domain>/<path>`, under a new schema version v0.3. No consumer,
updated or not, can present the claim as established without deliberately
stripping a prefix nothing told it to strip. A sibling field inverts that: every
consumer must consult it at every use site, forever.

And it did NOT need the lockstep 6.1 warned about. Accepting v0.3 is
deliberately not a MUST, so a consumer that has not decided what a claim means
to it refuses the event, which trailryx and `agent-conform` already do. 6.1's
sentence saying a subject kind would need every consumer to move together is
corrected in the spec rather than left standing.

Landed as agent-passport#36, agent-stack-go#26 plus tag v0.7.0, heraldyx#40 and
idryx#44, in that order: consumers before the producer, so no claimed event
existed until every reader either refused it loudly or showed the claim
inseparably.

**What is still true after it**, so nobody reads this as solved attribution:
a claim is still a self-declaration and satisfies no control requiring an
attested identity; an agent that unsets `AGENT_PASSPORT_ID` leaves the layer
entirely and its flows degrade to `proc:`, where `unmanaged_egress` still fires;
`proc:` findings still have no subject and never travel; and **trailryx still
records no `identity_finding` at all**, claimed or established, because its
mapper has no row for that type. That last one is separate from this gap and is
below.

**Re-check:** run any capture carrying a `claimed:` identity through
`idryx detect` with `IDRYX_EVENTS` set, and read the schema stamp on the
resulting events rather than only the counts.

### G4.6 trailryx records no identity finding at all, claimed or established

Opened 2026-08-10, found while closing G4.5 and worth its own entry because
closing that one is easy to misread as having delivered this.

`@measured` `grep -n 'identity_finding\|alert_sent'
trailryx/crates/trailryx-agentevent/src/lib.rs`: the mapper has a row for
`alert_sent` and none for `identity_finding`. So every finding idryx has written
since 2026-08-10, established and claimed alike, is refused at that door as
`UnknownType` and produces zero records.

**This is not the envelope's fault and G4.5 did not touch it.** The envelope
carries these events correctly; trailryx has simply never been told what an
identity finding IS in its own record vocabulary. Adding a row is a decision
about that vocabulary rather than a mapping chore: trailryx's records are the
part designed to be believed and kept, and its own invariant 7 governs what may
be appended to the type set.

Two questions inside it, and both are the user's:

- does an identity finding become a record at all, and under which record type;
- and what does invariant 35's tenant check do with a CLAIMED subject whose
  trust domain is not the receiver's? With an established subject a foreign
  domain is a misconfiguration. With a claimed one it can be a process naming
  another organisation's agent, in a store whose whole claim is that it is
  believed. Refusal should be its own counted rejection rather than folded into
  an existing one, so the count says what was turned away.

Until then trailryx refuses claimed events one layer earlier anyway, at
`UnknownSchema`, because it accepts only v0.1 and v0.2. That refusal is correct
and counted, and it means nothing is being lost silently.

**Closes when:** the mapper has a row for `identity_finding` and the tenant rule
says what it does with a claim.
**Re-check:** the grep above, and `trailryx-node events --file` against an idryx
journal, reading the refused count rather than the accepted one.

### G4.3 Three sources of truth about what each product emits, and only one is gated
The registry (SPEC 6.2) is gated against artifacts by C4, which is clean. What
is **not** gated is the registry against the producers' actual code. C4 checks
that nothing in `agent-passport` contradicts the registry; nothing checks that
the registry matches what tokenfuse, heraldyx and genaryx really write.
**Closes when:** a C7 reads each producer's emission sites and compares.

---

## 5. Ungated invariants, estate-wide

@measured `grep -c '(not enforced)'` across every `CLAUDE.md`, 2026-08-09.
These are invariants each repository has decided matter and that nothing but
prose holds. This is not a defect list; it is the map of where a silent
regression is possible.

| repo | ungated invariants (approx) | the ones worth a gate first |
|---|---|---|
| Qryx | 4 | the scanner's silent-zero behaviour |
| stack-up | 4 | "up.sh starts, down.sh stops"; sandbox telemetry must not look like production |
| taipan | 3 | a failure mode that is silence rather than an error |
| stack-k8s | 3 | "the stack is reporting silence, not health" |
| agent-stack-go | 3 | compatibility promises, and never copying a shared type |
| Engram | 2 | caveats kept beside numbers rather than rounded away |
| verdryx | 2 | the language boundary |
| stack-single | 2 | "correct once and impossible twice" |
| mockryx | 2 | widening a shared type upstream rather than locally |
| terraform-provider-taipan | 2 | never delete from the Registry, ship a patch |
| catalog | 2 | every template states what it does not cover |
| bank-in-a-box | 2 | stays local, no remote |
| tokenfuse | 2 | invariants 4 and 21 |
| trailryx | 5 | invariants 9, 10, 15, 17, 27 |
| agent-passport | 2 | invariants 1 and 6 |

**The pattern worth naming:** three of the top four are deployment repositories,
and every one of their ungated invariants is about a failure whose symptom is
silence. That is the estate's single most repeated defect shape, and it is
least gated exactly where it is most likely.

---

## 6. The six systemic classes

From the 2026-08-05 audit, restated with current status. Each is a shape that
recurred in several services independently.

1. **A guarantee exists as a function nobody calls.** Tested, unreachable,
   green. `@claude 2026-08-05.` Proposed gate: for every exported guarantee,
   require a caller outside `#[cfg(test)]` / `_test.go`. **Not built.**
2. **Silent zero: "could not look" is indistinguishable from "nothing there".**
   Named across qryx, engram, idryx and tokenfuse. Proposed rule: every scanner
   and connector prints "N unread, M skipped by size, K unparsed", and zero
   findings with N greater than zero is not green. **Not built.** This is the
   single highest-value estate-wide rule on this list.
3. **Accounting errs toward "more expensive", in a product whose promise is
   accurate accounting.** **Largely closed**, see section 8.
4. **The factory is described as one contract and held together by copies.**
   **Now gated** by estate-gates C1, C2, C3, C6. Currently red on C1 and C2, see
   section 1.
5. **The registry is honest in prose and not yet in artifacts.** **Closed**,
   gated by C4, which is clean.
6. **The emergency path is unavailable exactly when it is needed.** genaryx
   passkeys, G3.7. **Open.**

---

## 7. Design decisions taken and not yet built

Recorded so a decision does not evaporate between the session that made it and
the session that would have implemented it.

- **The web-egress enforcement point** (`scopyx`). Full design in
  `browse-plane-plan.md`. Name decided `@yurii 2026-08-09`. Three open
  questions in that file's section 14, one of which (fail-closed on an
  unreachable PDP) blocks implementation.
- ~~**`unrouted_egress` detector** in idryx, plus the emitter G4.1 needs.~~
  **Built**, idryx#43, 2026-08-10, and not as the design in G2.4 described it:
  the join that item specifies cannot be built, and the detector that works is
  the inversion of it. See G2.4.
- **A C7 cross-repo check**: the event registry against producers' code, G4.3.
- **The silent-zero rule** as an estate-wide convention, class 2 above.
- ~~**A subject kind for the envelope**, so a claimed identity can travel.~~
  **Built 2026-08-10**, and not as a subject KIND: the distinction lives inside
  the subject and the version stamp carries it. See G4.5.

---

## 8. Closed, with the evidence that closed them

Kept rather than deleted, so the next audit knows what was checked.

### Closed 2026-08-10

- ~~**G4.1: idryx emits nothing into the shared event envelope.**~~ **Closed.**
  idryx#40 gives it an `agent-event` sink alongside Slack and OTLP;
  agent-passport#33 takes its row out of RESERVED and registers
  `identity_finding`; C4 reads it as an ordinary producer.

  **What the build found that this register had not.** The first version
  validated idryx's own identity id against the envelope grammar, compiled,
  passed its tests and wrote NOTHING on a real run: idryx inventories
  `agent:ops-helper` and the envelope wants `agent://<trust-domain>/<name>`,
  which are different namespaces. The name comes from the inventory and the
  domain only from the operator, so `IDRYX_TRUST_DOMAIN` is required alongside
  `IDRYX_EVENTS`, and half-configuring refuses at startup rather than producing
  a journal that is forever empty. `@measured` 2026-08-10: six events with the
  right subjects from `testdata/demo_agents.json`, and zero events with a
  zero-byte journal and the count reported from `testdata/events.json`, whose
  findings are about people.

  **What that evidence did not cover, found 2026-08-10 and fixed in idryx#42.**
  It was measured on `testdata/demo_agents.json`, which uses idryx's own
  inventory namespace, `agent:ops-helper`. That was the namespace the writer was
  built for, and it was the only one it handled. Every identity that arrives
  ALREADY canonical, from a Passport document or from any bus producer, also
  begins with `agent:`, so the same two lines cut that prefix and prepended the
  operator's domain to a string that already carried a scheme.

  `@measured` 2026-08-10, two real runs: the journal received
  `agent://acme-bank.example///acme-bank.example/eng/standalone` and
  `agent://acme.example///acme-bank.example/support/tier1-bot`. The findings
  were not dropped, they were published about agents that do not exist, and
  `passport.ValidateAgentURI` accepted the shape because its pattern lets the
  path hold empty segments.

  The second is the one worth keeping. An agent of `acme-bank.example` came out
  carrying the OPERATOR's trust domain. trailryx invariant 35 compares exactly
  that field to decide whether it may record an event, so the defect did not
  merely corrupt a subject, it walked a foreign tenant's agent past the one
  check in the estate that exists to stop that. The function's own comment cites
  invariant 35 as the reason it must not invent a domain.

  **The lesson is about the evidence rather than the code.** A closure is only
  as wide as the namespace it was measured in. This one said "six events with
  the right subjects", which was true, and nothing in the sentence hinted that a
  second namespace existed. Where a producer accepts identifiers from more than
  one source, closing evidence should name which shapes it exercised.

  Two narrower faults of the same class were found by reviewing that fix and are
  closed in the same PR: a non-empty but invalid `IDRYX_TRUST_DOMAIN` wrote
  canonical subjects while silently dropping every inventory one, which is a
  journal that reads as whole while missing half the estate; and `agent://` or
  `agent:///bot` still built `agent://<domain>///`, the same fabrication one
  namespace narrower.

  **Not fixed, and it is upstream.** `agentURIPattern` in agent-stack-go is
  `^agent://[a-z0-9.-]+/[a-z0-9._/-]+$`. The `/` inside the path class permits
  empty segments, which contradicts SPEC 3.1's "one or more segments", and the
  domain class accepts `...` and `-` where 3.1 asks for a DNS name the
  organisation controls. Tightening it would have turned this defect into a
  counted skip. It is a shared wire contract in nine repositories and would
  start refusing identifiers that pass today, so it is a decision rather than a
  fix, and it belongs beside a sentence in SPEC 3.1 saying plainly what 3.1
  currently only implies.

### Closed 2026-08-09, the day this file was opened

- ~~**G4.2: no emitter validates `agent_id` against the `agent://` pattern.**~~
  **Closed.** All three now call the same predicate before writing, each at a
  line this register names rather than describes (`@measured` 2026-08-09,
  `grep -rn is_canonical_agent_id` across the three repositories):

  | repo | call site |
  |---|---|
  | tokenfuse | `crates/core/src/agent_event.rs:501`, added by tokenfuse#190, merged this day |
  | engram | `engram/engram/events.py:333` |
  | verdryx | `verdryx/verdryx/events.py:367` |

  **What they do is worth stating exactly, because "validated" would overstate
  it.** None REJECTS. Each writes the event, increments a nonconforming count,
  and warns once per distinct id behind a bounded set so a misconfigured agent
  cannot flood a log. That is the right choice for a trail nobody may silently
  drop from, and it is a different guarantee from refusal: a consumer reading
  these events still meets ids the envelope's own schema would reject. What
  changed is that the number is now true and visible instead of absent.

  **The README half closed too.** engram's example is now
  `agent_id="agent://acme.example/planner"`. The bare `"planner"` that the
  finding quoted is gone, so the docs no longer teach a value a strict consumer
  must reject.

  **The rule is now gated in four places rather than three.** C7 gained the
  tokenfuse row the same day, so the constant behind all of this is compared
  against agent-passport's schema in every repository that retypes it.

- ~~**G1.1: four consumers a minor behind on `agent-stack-go`.**~~ **Closed.**
  All six now pin `v0.6.0`: heraldyx#35, mockryx#27, wardryx#19,
  terraform-provider-taipan#16, and qryx and idryx direct to `main` under their
  own push-to-main loops. C1 clean.

  **What reading the delta changed.** The four were not moved to `v0.5.1`, the
  tag C1 was pointing at. `chain`, `event` and `passport` were byte-identical
  across `v0.4.0` and `v0.5.1`, so the "different contract" the gate reported
  was, for that delta, no contract at all. What the delta did carry was G1.4.

- ~~**G1.4: the `v0.5.1` tag ships a 4.8 MB build artifact.**~~ **Closed** by
  cutting `v0.6.0` from `main`, which has no `agent-conform` at the module root.
  @measured `git ls-tree v0.6.0 --name-only`, 2026-08-09: absent. The release
  workflow published six assets and the module zip no longer carries the
  artifact.

  `v0.5.1` still has it and always will. Deleting a published tag is not the fix
  and was not proposed.

- ~~**G1.2: three vendored schema copies disagree and one is gone.**~~
  **Closed**, and the four findings were three different things:

  - genaryx's two copies were a real defect. They are compiled in with
    `include_str!` and are what `Conformer` validates against, so the console
    accepted a delegation chain of any depth while reporting it had validated
    one. genaryx#17 restores the bytes **and** adds a test asserting both
    directions, verified red against the unfixed schemas first.
  - verdryx's fixture was the same missing bound one layer down. verdryx#19,
    same treatment, same red-first check.
  - engram's "missing copy" was not drift at all. engram migrated to v0.2 on
    2026-08-06 and deleted the v0.1 fixture as part of it. The record here was
    stale, and the entry **moved** to the v0.2 list rather than being deleted,
    because engram still vendors a copy that was in no list at all. estate-gates#2.

- ~~**C5's only finding: a stale expectation for `verdryx-drift`.**~~
  **Closed**, estate-gates#3. The entry had written its own end date into its
  reason, the CronJob landed on `stack-k8s` `main`, and the entry was deleted
  rather than edited, exactly as it asked.

  This is the one closure that was not a defect anywhere: invariant 7's second
  half working as designed.

### Security items, all seven re-verified against the code 2026-08-09

- ~~**G3.1 tokenfuse: `/v1/ingest` authorised through `org_for`.**~~ **Closed.**
  `crates/cloud/src/http.rs:668` calls `st.authorize_mutation("POST",
  uri.path(), &body, &headers)`. A viewer key can no longer inject records that
  raise a High incident, get mailed, and feed the compliance counts.

- ~~**G3.2 the MCP broker skipped its policy gate with no identity header.**~~
  **Closed.** `needs_identity` in `mcpbroker.rs` refuses a `tools/call` that
  names no agent while Wardryx is enforcing. HTTP answers with the same 400 the
  LLM path returns, byte for byte, and stdio with its own JSON-RPC code
  `-32007`, deliberately distinct from the deny code: a refusal because the gate
  could not RUN is a different fact from one the gate decided.

- ~~**G3.3 rug-pull detection rested on `DefaultHasher`.**~~ **Closed.**
  `crates/core/src/mcp.rs:118` is SHA-256 over a domain separator with each part
  length-framed, because tool names, descriptions and schemas are
  attacker-controlled strings that may contain any delimiter. `Lock` gained the
  `algorithm` and `version` fields whose absence the finding named.

- ~~**G3.6 qryx verified a signature against a key inside the same
  document.**~~ **Closed** today, qryx `375cbb7`. `--signer` pins the
  fingerprint and a mismatch names both keys. Unpinned still works, and what
  changed for those callers is the sentence: the tool said `VERIFIED`, which
  reads as authentic, and now says the document is consistent and self-signed
  and that this establishes nothing about who signed it.

  The test asserts the defect as well as the fix. It signs one report with two
  keys and requires the unpinned form to ACCEPT the forgery and report the
  forger's key, so the day that path starts refusing, somebody decides it here
  rather than discovering it in a customer's pipeline.

- ~~**G3.7 genaryx could not delete or revoke a passkey.**~~ **Closed, and it
  had been since 2026-08-05**, four days before this register claimed
  otherwise. `webauthn.rs:250` has `remove`, `main.rs:292` routes it,
  `REMOVE_PASSKEY_CEREMONY` exists, a separate factor is required to remove the
  LAST enrolled key, and
  `a_passkey_is_removed_by_a_caller_who_confirms_with_an_enrolled_one` covers
  it. genaryx's own CLAUDE.md records both halves being fixed together.

  **Why this register said otherwise is the part worth keeping.** The re-check
  was `grep 'fn add\|fn remove\|...' | grep -i passkey`, which requires the
  word `passkey` on the same line as the signature. `pub fn remove(` does not
  carry it. A two-stage grep that ANDs across one line is a check that reports
  absence it never looked for, which is invariant 19's shape in the tooling
  used to audit rather than in the code audited.

- ~~**G3.8 genaryx had no way to make the ceremony mandatory.**~~ **Closed.**
  `GENARYX_WEB_REQUIRE_PASSKEY` exists; with it on and nothing enrolled, a
  sensitive command is refused with an error saying how to enrol, rather than
  running on the session cookie. Still opt-in, so the guarantee is
  configuration-dependent until a box sets it, which genaryx's own invariant
  marker says.

- ~~**G3.5 trailryx federation returned everything to any valid
  certificate.**~~ **Closed as a correction rather than as a fix**, trailryx
  `47eb0d9`. The claim was wrong about what ships: `serve` is reached only from
  the tests and from `fed-probe`, which calls itself deliberately not a service,
  and no production federation server exists. What was real is that the only
  implementation of the answering half ignores the predicate and said nothing
  about it. Now the doc comment says so, the binding is named
  `_predicate_is_not_applied_here`, `VALIDATION.md`'s "Not yet measured" carries
  it, and `a_predicate_does_not_narrow_what_this_harness_answers` pins the
  behaviour so it goes red the day filtering arrives.

### Closed before this file existed

- ~~**verdryx mirrored seven of tokenfuse's nine blocked-decision strings**,
  counting avoided estimates as real money.~~ **Closed.** @measured
  `verdryx/verdryx/costper.py:74-90`, 2026-08-09: the set now carries
  `unit_budget_exceeded` and `identity_mismatch`, with a comment naming the
  tokenfuse commit that added them.
- ~~**idryx stored XSS in the dashboard**: `esc()` where `escJS()` was needed in
  an `onclick` string, with a regression test that checked the wrong
  property.~~ **Closed.** @measured `Idryx/internal/server/xss_test.go`,
  2026-08-09: a test now asserts the property directly, that no ingested data
  can close a JS string literal, and names the fix in its failure message.
- ~~**tokenfuse settled a failed provider call at the pre-flight estimate**,
  charging a run for calls nobody billed.~~ **Closed for the buffered path** in
  PR #167, and the streaming path now passes `provider_refused` into
  `SettleGuard::new` alongside the reservation. @measured
  `tokenfuse/crates/gateway/src/proxy.rs:1240-1252`, 2026-08-09. Read
  `SettleGuard` before quoting this as fully closed.
- ~~**trailryx had no ingest for the shared event envelope.**~~ **Closed.**
  `crates/trailryx-agentevent` exists and maps envelope types onto record
  types, refusing an unmapped type by name. The
  `heraldyx-notifications-plan` memory still says otherwise and is stale.
- ~~**The event registry claimed idryx as an emitter in three artifacts.**~~
  **Closed and gated**, estate-gates C4, clean on 2026-08-09.

---

## 9. What has not been checked

Named so the shape of the unexamined is visible. This section is as important
as section 3.

- ~~Six of the eight items in section 3 have not been re-verified.~~ **Done
  2026-08-09.** All seven open ones were opened against the code; six closed,
  one was a wrong finding and is corrected in place. The prior held: the audit
  that recorded them was recording work that was already being done.

  **What the pass got wrong about itself is the more useful result.** One item
  was reported still open on the strength of a grep that ANDed two conditions
  onto one line and therefore could not see the function it was looking for.
  A re-check is a check, and a check that cannot fail correctly reports
  whatever the auditor already believed. Where a finding says a thing does not
  exist, the evidence should be the file read, not a pattern that did not
  match.
- **No CI status was read.** No claim here about whether any repository's
  pipeline is green.
- **No connector was checked against a real cloud account.**
- **Nothing was built or run** except the estate-gates suite and three greps.
  Test counts anywhere in the estate are unverified by this document.
- **The mobile and Sphere repositories were not looked at at all.**
- **`taipan`, `catalog` and `bank-in-a-box`** contributed only their ungated
  invariant counts; their code was not read.
- **Whether the four v0.4.0 pins in G1.1 actually break anything** is unknown.
  The gate proves they differ, not that the difference bites.

---

## 11. G3.8, the blocker that was ours

Numbered as a section rather than folded into 3, because it was found after
this file's own section 10 had already stated it wrongly, and the shape of the
mistake matters more than the outage.

### G3.8 A stale local advisory database blocks every Rust audit in the estate, and looks exactly like an upstream outage

**What was claimed here on 2026-08-09**, in section 10 and in the commit that
opened it: that the RustSec advisory database carried `RUSTSEC-2026-0244` in
both `crates/gettext-rs/` and `crates/gettext-sys/`, that upstream had been
broken for hours, and that nothing on our side could fix it.

**What is actually true**, measured the same day. Upstream fixed it properly
and hours earlier, in `e12b689b`, as a clean git rename of the file from one
directory to the other. `git grep -l RUSTSEC-2026-0244 HEAD -- crates/` returns
exactly one path. The second copy existed only in the local checkout, as an
untracked directory `git status` reports as `?? crates/gettext-sys/`, beside
eight other untracked `RUSTSEC-0000-0000.md` placeholder files left over from
earlier assignment rounds.

**Why it was permanent.** `cargo audit` fetches by pulling into
`~/.cargo/advisory-db`, and `git pull` never removes an untracked file. It then
reads the DIRECTORY rather than git `HEAD`, so any stale file that ever landed
there is loaded as an advisory forever, and every subsequent fetch reports
success while the audit stays broken. `git clean -fd` fixed it in one command,
after which the database loaded 1198 advisories and `tokenfuse/scripts/audit.sh`
exited 0 (`@measured` 2026-08-09).

**How to re-check it.** Never `ls` the directory, which is what produced the
wrong finding:

```bash
git -C ~/.cargo/advisory-db status --short          # untracked leftovers
git -C ~/.cargo/advisory-db grep -c RUSTSEC-0000-0000 HEAD -- crates/ | wc -l
```

The first is the whole diagnosis. Anything in it is a file no upstream fix will
ever remove.

**What generalises.** `ls` reads what a tool reads; `git` reads what upstream
published. When the question is "is upstream broken", only the second answers
it, and the first will confidently say yes about a mess of your own. This is
the same defect class as the G3.7 miss recorded in section 9, one layer out: a
re-check that cannot distinguish "they broke it" from "we did" reports whatever
the auditor already believed.

**Not fixed anywhere but this machine.** The clean was local. Nothing prevents
the same accumulation on any other machine, in any Rust repository in the
estate, and the symptom will again be a red `security` job that looks like
somebody else's problem. The cheap guard is for `scripts/audit.sh` to refuse
when its database checkout is dirty, and say which files, rather than letting
cargo-audit fail with a parse error several layers from the cause. **Not
built**, and it belongs in tokenfuse and trailryx rather than here.

**CI was never affected.** `Swatinem/rust-cache` does not cache
`~/.cargo/advisory-db`, so every CI run clones it fresh. The red on tokenfuse
#190 was the FIRST breakage of the day, a `RUSTSEC-0000-0000.md` placeholder
that upstream really did publish under `crates/gettext-rs/` (`e11d6b33`
through `e0bc1e80`) and really did fix. Those are two different outages and
this file previously ran them together.

---

## 10. Estate-wide standing decisions

Different in kind from everything above. Sections 1 to 9 are findings about
what exists; this one is decisions about what gets built next. They live here
because they are cross-repository by nature and this is the only repository
allowed to be.

### D1. Go is the default for new services. Rust stays where it earns it.

`@yurii 2026-08-09`, in his words: "я так розумію, що на наступні якісь
сервіси, які ми будемо робити, ми будемо використовувати скоріше мову Go...
Тобто я дивлюсь, що треба використовувати все-таки Go, там якийсь TypeScript,
якщо треба щось намалювати." Confirmed the same day: "запиши цей дефолт в
estate-gates".

**The decision.** A new service in this estate is written in Go unless there is
a stated reason it cannot be. TypeScript for anything with a user interface.

**What it does not mean.** Nothing is rewritten. tokenfuse, trailryx, genaryx
and taipan stay in Rust, and a change that touched them only to change language
would trade working, gated code for an unmeasured rewrite.

#### The reasons he gave, separated by what actually holds them

He named slow compilation and a machine pushed to full load. Both are real and
they have three different causes, which is worth keeping apart because only one
of them is the language.

1. **Build cost, which is mostly the dependency graph.** trailryx pulls
   DataFusion and every fresh worktree rebuilds it from nothing, which is why
   this Mac needs sccache and `jobs = 4` in `~/.cargo/config.toml` to be usable
   at all. trailryx CI was 56 minutes before optimisation and 13 after
   (`@measured` 2026-08-04). By comparison scopyx runs `go vet`, `staticcheck`,
   `go build` and `go test -race` over 17 files and an 11-module graph in
   **3.76 seconds** with the test cache cleared (`@measured` 2026-08-09,
   `cd ~/Development/scopyx && go clean -testcache && time sh -c 'go vet ./... && staticcheck ./... && go build ./... && go test -race ./...'`).
2. **Ecosystem tooling, and this one is not the compiler at all.** `cargo
   audit` refuses to load the ENTIRE advisory database when one advisory in it
   is malformed, so a single bad file upstream stops every audit in the estate
   rather than affecting the crate it concerns. `--ignore` does not help: the
   failure is at database load, before any ignore is evaluated (`@measured`
   2026-08-09, `cargo audit --ignore RUSTSEC-2026-0244` in tokenfuse still
   exits on `error loading advisory database`). Go's `govulncheck` queries a
   hosted database and has no equivalent whole-database failure mode.
   `@claude`

   **The example first written here was wrong, and the correction is D1's most
   useful part.** See G3.8, opened the same day this section was.
3. **Our own configuration**, since fixed. Not a property of anything.

#### What Go costs, stated rather than left for later

`@claude`. Go has no sum types, so scopyx's `Verdict` is an `int` with
constants instead of an enum the compiler forces every reader to exhaust, and
adding a verdict will not break a `switch` that ignores it. It has no way to
make "this struct may never carry a caller-supplied header" a type, which is
exactly why scopyx holds that invariant in `scripts/no-caller-headers.sh`, an
anchor over the source tree rather than a compiler error. We are trading
compiler guarantees for cycle time. For a small network process that decides,
records and forwards, that is the right trade. For a query engine, a byte-exact
format or an embedding index it is not, and those are the cases where Rust
stays correct.

#### The census this rests on

`@measured` 2026-08-09, by looking for `go.mod`, `Cargo.toml`, `package.json`
and `pyproject.toml` at the top level and one directory down in each of the 19
repositories `estate.json` records.

| language | repositories |
|---|---|
| Go | agent-stack-go, heraldyx, idryx, mockryx, qryx, terraform-provider-taipan, wardryx |
| Rust | genaryx, taipan, tokenfuse, trailryx |
| Python | engram, verdryx |
| none of the four | agent-passport (a spec), bank-in-a-box, catalog, stack-k8s, stack-single, stack-up |

TypeScript is present inside `genaryx/apps/web`, `tokenfuse/cloud/dashboard`
and `tokenfuse/sdk/js` rather than as any repository of its own. Go was already
the plurality before this decision was taken; the decision makes an existing
practice explicit rather than changing direction.

**One correction the measurement produced.** Engram is Python, not Rust. It was
recalled as Rust here, and recall is what this file's provenance rules exist to
stop from becoming a permanent claim.

**scopyx is not in `estate.json`** (`@measured` 2026-08-09,
`grep -c scopyx estate.json` returns `0`), so the census covers 19 repositories
and there is a twentieth that no cross-repo check reads. Open, and separate
from this decision.

#### How this is held

*(not enforced: nobody can check a choice before the repository exists)*

The part that IS structural is drift after the fact. `estate.json` records a
role per repository and no language, so nothing notices a Go service that grows
a crate or a Rust repository that quietly becomes the fifth. Giving each entry a
`language` field and comparing it with the manifest files present would catch
that, and would make the census above self-refreshing rather than a snapshot
with a date on it. Not built. It is the smallest useful gate on this section
and it would subsume the census by hand.
