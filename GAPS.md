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

@measured `./run-gates.py --mode ref --ref origin/main`, 2026-08-09:
**3 of 6 gates found drift (C1, C2, C5). C3, C4 and C6 are clean.**

**The mode is part of that claim.** CI runs `--mode clone`, where `taipan` is
private and `bank-in-a-box` has no remote, so C4 reports **partial, something
went unmeasured** rather than clean. Both readings are true of their own mode.
Anybody comparing this section against the red badge should expect that one
difference and no other.

### G1.1 Four consumers are a minor behind on the shared contract module

`agent-stack-go` is at **v0.5.1**. Pinned at **v0.4.0**: `heraldyx`, `mockryx`,
`qryx`, `wardryx`. Current: `idryx`, `terraform-provider-taipan`.

The module is pre-1.0, so a minor bump is where behaviour and breakage live.
Four services are on a different contract from the two that are current.

**Closes when:** four `go.mod` bumps, each with its own PR and green CI.
**Re-check:** the C1 section of the gate run.
**Note:** this is the same class that cost a real defect before, when idryx sat
on v0.3.0 and the delta was the chain verifier idryx most needed.

### G1.2 Three vendored schema copies disagree with the canonical one, and one is gone

- `genaryx:crates/core/src/schemas/agent-event.v0.1.schema.json` and
  `...v0.2.schema.json` both **omit `maxItems: 32`** on `on_behalf_of`.
- `verdryx:tests/fixtures/agent-event.v0.2.schema.json` omits the same.
- `Engram:tests/fixtures/agent-event.schema.json` is **absent**, while the
  gate's record says engram vendors it there.

**Why this is a security item and not housekeeping.** `maxItems: 32` is SPEC
§5.1's delegation-chain depth cap. genaryx compiles its copy into
`genaryx-core` with `include_str!` and validates against it, so the console
accepts a delegation chain of any depth while believing it validates one. The
same for verdryx's test fixture, which means its suite cannot catch a chain
that violates the spec it claims to conform to. And engram's missing file is
the worse shape: something that used to be validated is not, and nothing said
so.

**Closes when:** the three copies are byte-identical to canonical, and engram's
copy either returns or the gate's record is corrected to the new path.
**Re-check:** the C2 section of the gate run, which prints the diff.

### G1.3 Deployment parity: stack-single schedules nothing at all

`stack-single` installs **no governance routine of any kind**: no cron, no
timer, no supervisor, no periodic compose service. Not `focus-export`, not
`idryx-detect`, not `qryx-trend`, not `verdryx-drift`. @measured by C5,
recorded 2026-08-06 and still true 2026-08-09.

`stack-k8s` is missing one: `focus-export` has no CronJob, so a Kubernetes
install produces no FOCUS export at all.

The single-box deployment brings the planes up without the scheduled work that
keeps them producing. A box that looks installed and is not governing itself is
the exact failure mode the estate's own "silent zero" rule is about.

**Closes when:** the routines exist in both, or the absence becomes a recorded
decision rather than a recorded gap in
`estate-gates/expectations/deployment-parity.json`.
**Re-check:** the C5 section of the gate run.

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

Items below carry their verification date. **Only two were re-verified on
2026-08-09** (both closed, see section 8). The rest are carried from the
2026-08-05 audit and are marked as such: they are real findings that have not
been re-checked, not current claims.

### G3.1 tokenfuse: `/v1/ingest` authorises through `org_for`, not `authorize_mutation`
`@claude 2026-08-05, not re-verified.` A viewer-level key can inject records
carrying `decision: "budget_exceeded"`, raising a High incident that is
exported to the shared NDJSON and **mailed by heraldyx**; the same path feeds
`decision_counts`, from which `/v1/compliance` derives evidence for a regulator.
The neighbouring `/v1/findings` is admin-gated with a comment reasoning about
exactly this difference.
**Re-check:** compare the authorisation call at `/v1/ingest` with `/v1/findings`.

### G3.2 tokenfuse MCP broker: the policy gate is skipped when the identity header is absent
`@claude 2026-08-05, not re-verified.` No header, no Wardryx gate, and secret
injection proceeds anyway. The LLM path in the same repository returns 400 for
the same absence. Two enforcement points, one missing header, opposite refusal
postures.
**Re-check:** the `x-fuse-agent-id` branch in `mcpbroker.rs` against the one in
`proxy.rs`.

### G3.3 tokenfuse: rug-pull detection rests on `DefaultHasher`
`@claude 2026-08-05, not re-verified.` SipHash with a zero key, truncated to
u64, in a lockfile with no algorithm or version field. The key is public, so
there is no MAC property. Worse operationally: `rust-toolchain.toml` is
`stable` and the action builds the scanner from source on every run, so a
change to Rust's default hasher flips **the entire consumer fleet at once**
into Critical "RUG PULL", and the recovery action (re-pin the lockfile) is
exactly the action that masks a real rug pull.
**Re-check:** the hasher and the lockfile's fields in the MCP scan path.

### G3.4 trailryx: the SQL read surface never filters a row
`@yurii-adjacent, recorded as a deliberate constraint.` This is **not a defect**
and is listed so it is not mistaken for one: trailryx invariant 27 states the
surface admits or refuses a connection and never filters a row, with the
deployment model being one server per scope. The risk is documentation drift:
its own unit tests, read without that line, look like tenant isolation and
teach the opposite conclusion.
**Closes when:** nothing. It stays true or it is replaced, never quietly.
**Watch for:** the day row filtering is added, this line must be replaced
rather than deleted.

### G3.5 trailryx: federation `PeerService::query` ignores the predicate
`@claude 2026-08-05, not re-verified.` Possession of a certificate that chains
to the CA equals full read of whatever the peer was configured with.
**Re-check:** whether `query` applies its predicate before answering.

### G3.6 qryx: `verify-evidence` checks a signature against a key inside the same document
`@claude 2026-08-05, not re-verified.` No flag pins an expected signer. As a CI
step it is a check that cannot fail against a forgery, which is trailryx
invariant 19's shape in another repository.
**Re-check:** whether an expected-signer flag exists.

### G3.7 genaryx: no way to delete or revoke a passkey, and registration is protected by the session it protects against
`@claude 2026-08-05, not re-verified.` `PasskeyStore` had `add` and
`update_sign_count` and nothing else, so a user who lost their only
authenticator gets 428 forever on all five sensitive commands, curable only by
editing `passkeys.json` on the box that is reached through that console. Beside
it: a stolen admin session on a box where nobody has registered yet can
register its own key and pass the ceremony honestly.
**Re-check:** grep `PasskeyStore` for a removal method, and read `webauthn_gate`.

### G3.8 genaryx: the WebAuthn ceremony has no configuration that makes it mandatory
`@claude 2026-08-05, not re-verified.` `webauthn_gate` returns `Ok(None)` as
soon as a user has no key, so all five sensitive commands fall back to the
session cookie.
**Re-check:** read `webauthn_gate` for the no-keys branch.

---

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

- **Six of the eight items in section 3 have not been re-verified since
  2026-08-05.** Given that three of three re-checked items turned out to be
  closed, the prior for the remaining six is that some are already fixed.
  Re-verifying them is perhaps two hours and it is the highest-value work in
  this file.
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
