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

@measured `./run-gates.py --mode ref --ref origin/main`, 2026-08-09, second run
of the day: **all 6 gates clean, and every subject was measured.**

The first run of the day found three gates drifted. All four findings across
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

### G4.1 idryx emits nothing into the shared event envelope
@measured `agent-passport/SPEC.md` §6.2, 2026-08-09: idryx's seven event types
are listed **RESERVED, not emitted**. Its detections leave by OTLP and by Slack.

Consequence, and it is why G2.4 is only half a solution: any detector idryx
gains, including an `unrouted_egress` one, produces a finding that reaches
neither heraldyx nor trailryx, because it never enters the bus they read.

**Closes when:** idryx has an event writer and SPEC 6.2's row stops saying
reserved.

### G4.2 `agent_id` is not validated against the `agent://` pattern by any emitter
`@claude 2026-08-05, not re-verified.` Not engram, not verdryx, not tokenfuse.
Meanwhile engram's own README shows `agent_id="planner"`, so the canonical
example in the docs produces a value a strict consumer must reject.
**Re-check:** grep the emitters for a pattern check before write.

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
- **`unrouted_egress` detector** in idryx, plus the emitter G4.1 needs. Design
  in this file, G2.4.
- **A C7 cross-repo check**: the event registry against producers' code, G4.3.
- **The silent-zero rule** as an estate-wide convention, class 2 above.

---

## 8. Closed, with the evidence that closed them

Kept rather than deleted, so the next audit knows what was checked.

### Closed 2026-08-09, the day this file was opened

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
