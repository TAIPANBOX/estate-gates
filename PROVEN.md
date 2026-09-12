# What has actually been run, when, and by what

Companion to `OUTSIDE-VIEW.md`. That file is regenerated and answers "what does
a stranger find". This one cannot be regenerated, because it records **runs**,
and answers the question that keeps being answered from memory and answered
wrong: **has this ever actually been executed, on what, and when.**

## The rule this file exists to enforce

A line in a handoff that says "not proven" is scoped to the change it was
written beside. It is not a statement about the component. On 2026-09-01 a
scoped line about one environment variable was read as "this launcher has never
been brought up", and that wrong claim was carried into a report and into two
answers before it was checked. The same session also claimed Linux was never
tested, with three clouds' evidence sitting on disk.

So every row below carries **three** things and is refused without them:

1. **When**, as a date, never "recently".
2. **On what**, as a machine or a cluster, never "in CI" unless CI is the subject.
3. **The artifact**, as a path or a command somebody else can open.

And every row states its **scope**, because a run proves what it ran and
nothing adjacent. "GCP passes" measured on one cluster is not "GCP works".

## Refreshing this file

For the outside view, run the script; do not edit by hand:

```
./scripts/outside-view.py --write OUTSIDE-VIEW.md
```

For this file, add a row when a run happens. Never promote a row from reasoning:
a claim becomes `proven` only after a run, and only the run's own output moves it.

---

## Deployment, proven

| What | When | On what | Artifact | Scope |
|---|---|---|---|---|
| Five-node k3s cluster, all planes answering | 2026-07-25 | Hetzner, 5 x CPX42, Ubuntu 26.04, `fsn1` | `stack-k8s/evidence/cluster-verified.md`, `loadbalancer-verified.md`, `freeze-test-verified.md`; `PORTABILITY.md` §1 | about 25 min bring-up; `security-tests` 23 passed, 1 noted |
| The same stack on AWS | 2026-07-25 | self-managed k3s on EC2, 5 nodes | `stack-k8s/cloud/aws/evidence/aws-run-verified.md` | about 24 min; `cluster-verified` 10/0; `security-tests` 22 passed, 0 failed, 2 noted |
| The same stack on GCP | 2026-07-26 onward | 5 x `c2d-highcpu-8`, `europe-west3` | `PORTABILITY.md` §3 | 28 min 44 s at five nodes; `cluster-verified` 10/0; `security-tests` 24 passed, 0 failed, 2 noted. The load balancer never passed traffic: GOTCHAS 69, open, and marked Platform |
| `stack-single` installed and running on a clean machine | 2026-08-02 | one AWS `c7i.2xlarge`, since destroyed | `Execution journal/live-runs-2026-08-02.md` items 1 to 4 | Four defects found and fixed (stack-single#9, #10, heraldyx#4, `.env` quoting). Proof it ran: heraldyx delivered a live alert from the box |
| Node builds nothing; every pinned image pulled | 2026-09-01 | GCP cluster, five that day plus one AWS | `Execution journal/deployments.md` §3.1 | Deploy 17:16 to 13:32 to 11:33. `verify.sh` 12/0, `security-tests.sh` 27 passed / 0 failed / 3 noted. USD 4.78 for the day, both clouds verified empty afterwards |
| `stack-single`, three installs of the same box, same day, same machine type | 2026-09-01 | three GCP `e2-standard-2`, 2 vCPU, Ubuntu 26.04, each a fresh box, all destroyed | `go-to-market-2026-09/evidence/stack-single-three-installs-2026-09-01.md`, which carries the stamps, the exit codes, the check counts and the pull list. The full install logs are NOT there: they lived on the three boxes and were not copied off before the teardown, and the evidence file says so rather than implying otherwise | **Compiling everything (pre-#27): 51 minutes and it had not finished**, 9 of 10 images built, still on the console. **Planes pulled, door built (#27): 442 s**, exit 0, ten containers, 18 checks `ok`. **Nothing compiled at all (#28): 111 s**, exit 0, nine containers plus `init-volumes` exited 0, 19 checks `ok`, 0 failures, console 200, every image from ghcr.io. The first was stopped rather than finished, so its figure is a floor and not a total |
| `stack-up` from a cold cache on macOS | 2026-09-01 | this Mac, Apple Silicon, empty `CARGO_HOME` / `GOMODCACHE` / `GOCACHE` / npm cache, fresh `STACK_UP_HOME` and `TAIPAN_HOME` | `go-to-market-2026-09/evidence/stack-up-cold-run-2026-09-01.log` | 399 downloads, 353 compiles, zero reuse. **221 s** to a working dashboard; 10 records sealed, packed, verified offline, `VERIFIED`, exit 0. Run with `--no-tools`, so four installed-not-started tools sat outside it |
| The 2026-08-31 `WARDRYX_DSN` to `WARDRYX_DB` change (stack-single#26), through a full `stack-single` bring-up | 2026-09-01 | three GCP `e2-standard-2`, destroyed (the same three installs above) | `go-to-market-2026-09/evidence/stack-single-three-installs-2026-09-01.md`, plus `install.sh:691-702` for the check names | Both installs on top of #26 (stack-single#27 and #28) ran `install.sh`'s own section 8, which is where `WARDRYX_DB` is read: `wardryx answers inside`, `policy store is up`, `policy plane accepts its admin key` (200), `policy plane rejects an unknown key` (401), `gateway's key cannot write policy` (403), `wardryx is NOT on the host`, all `ok` in both runs (18 and 19 checks respectively, 0 failures). Exercised through `install.sh` and `docker compose up`, by the installer's own checks, not by a separate test |

## The gateway against a real provider, proven

| What | When | On what | Artifact | Scope |
|---|---|---|---|---|
| The released `tokenfuse:v0.4.4` image in `enforce` mode in front of `api.anthropic.com` (Messages door), a half-cent per-run budget, the breaker refusing the third call with `402 budget_exceeded` and exporting two `breaker_tripped` events with a `prev_hash` chain | 2026-09-12 | this Mac, Docker Desktop 29.7.2, linux/aarch64, the image pulled by tag | `go-to-market-2026-09/evidence/1.0/r3-anthropic-2026-09-12/` (`SUMMARY.md`, `calls.log`, `hdr-*.txt`, `body-*.json`, `events.ndjson`) | One door, one provider, one run, four calls, `claude-haiku-4-5-20251001`, about USD 0.0004. A first attempt sized its budget so that eight calls fit under it and saw eight 200s, which is recorded, not a defect. Not the OpenAI door (unreleased on main at that hour), not streaming, not a cluster |

## Sensors, proven

| What | When | On what | Artifact | Scope |
|---|---|---|---|---|
| Idryx's eBPF sensor (`idryx ebpf-capture`) attached and captured live traffic | 2026-09-08 | this Mac, Docker Desktop 29.7.2, LinuxKit kernel **7.0.12 aarch64**, BTF present (6 710 304 bytes), privileged container with `tracefs` mounted; binary cross-built `GOOS=linux GOARCH=arm64` | `evidence/captured.json` (21 flows) and `evidence/captured-pidhost.json` (2 flows) | The CO-RE program loads and attaches on arm64 and on a kernel it was never built against, which is the portability claim `connect.c` makes over tokenfuse's x86_64-only radar. It reported `proc:wget` and `proc:nc` connections correctly and counted 36 non-INET connects it deliberately skipped. **It has never run on a real fleet, a real cloud host, or against a real agent**; a 12-second capture in a container is not a deployment |

**What that run found: two defects, both reproduced, neither a named
limitation.** Checked before calling them that: SECURITY.md and README name no
container or PID-namespace caveat, and `identity.go` reasons about "fifty
containers each running the same binary", so a containerised sensor is inside
the intended envelope.

1. **The self-filter does nothing under a PID namespace.** `connect.c` reports
   `bpf_get_current_pid_tgid() >> 32`, the PID in the initial namespace;
   `capture_linux.go` compares it with `os.Getpid()`, the namespaced PID inside
   a container. Without `--pid=host` the sensor reported **16 of its own 21
   flows**; with `--pid=host`, which aligns the two and changes nothing else,
   2 flows and zero self-attributed (`evidence/captured.json` against
   `evidence/captured-pidhost.json`). The same PID is handed to
   `claimedAgentURI` for a `/proc` read, which SECURITY.md already calls worse
   than reading nothing.

2. **A Go program that merely resolves an LLM hostname is graded as having
   reached that API, HIGH.** When a name returns two or more addresses, Go's
   resolver sorts them per RFC 6724 and, to learn a source address for each
   candidate, `connect()`s a UDP socket to **every candidate on port 53**
   (`net/addrselect.go`, `srcAddrs`), sends nothing, closes. The tracepoint
   sees each one. `evidence/lookupprobe.go` (20 lines, only `net.LookupHost`)
   run under the sensor with `--pid=host` produced 8 flows to
   `generativelanguage.googleapis.com:53`, 2 to `api.openai.com:53` (exactly
   the A-record counts; anthropic returns one address, so no sort and no flow)
   and 6 to the resolver (`evidence/captured-probe.json`). Then
   `idryx detect -format json -source egress` on that file:
   **`unmanaged_egress` HIGH, "unattributed process reached an external LLM API
   directly (Google Gemini, OpenAI)"**, plus `shadow_ai` medium
   (`evidence/detect-captured-probe.json`). `matchLLM` strips the port before
   matching, so `:53` is graded exactly like `:443`.

   Finding 2 is why finding 1 looked the way it did: the sensor's own
   `resolveLLMHosts` is precisely such a Go lookup, so under a PID namespace the
   sensor files the HIGH finding against itself (`evidence/detect-captured.json`,
   `proc:idryx`, HIGH). Any Go agent, SDK or health check on a monitored host
   that resolves these names will draw the same HIGH.

The first write-up of this run, earlier the same day, explained the labels as
`destination()` mapping resolver traffic back to hostnames. **That was wrong**:
the labels are correct and the connects are real syscalls; the error is in
grading a port-53 connect as API egress. Corrected after the probe run, and left
here so the wrong explanation is not rediscovered.

Finding 2 is fixed: TAIPANBOX/idryx#68, squash-merged to `main` as `2717c4a` on 2026-09-08 after a green CI. Finding 1 is TAIPANBOX/idryx#66; its fix (TAIPANBOX/idryx#69, squash-merged to `main` as `19461f7` on 2026-09-08 after a green CI) hands the program the sensor's own PID namespace and decides self on `bpf_get_ns_current_pid_tgid()`. **Re-run of the exact #66 procedure on the fixed build, 2026-09-08, same Docker kernel, no `--pid=host`:** 3 flows, **0** the sensor's own (was 16 of 21), and a neighbour's `AGENT_PASSPORT_ID` read as `claimed:agent://acme.example/probe` (`evidence/fixed-nopidhost.json`; `fixed-pidhost.json` is identical in shape). Not exercised by that run: the initial-namespace branch of the `/proc` addressing, because Docker Desktop's "host" PID namespace is itself nested. Both are closed on `main` as of 2026-09-08. Fixing 1 needed a namespace-aware notion of self (`NSpid` from
`/proc/self/status`, or the sensor's own cgroup id, which every event already
carries). Fixing 2 is one condition: a connect on port 53 is name resolution,
not egress, whichever address it went to. tokenfuse's radar shares finding 2 by construction (`is_llm` flagged a provider
address on any port, and its BPF program takes UDP connects too); read off the code
on 2026-09-08, not run, since radar is x86_64-only. Fix: tokenfuse#263, squash-merged as `bbf48cf` on 2026-09-08 after the radar
job's re-run went green; the recorded red is a standalone rustc harness of the
same function, because ci.yml runs on pull_request only. The first CI run of
that PR failed on `System deps`: snapshot.ubuntu.com served 502/503 on every
dated snapshot for hours, and a re-run hung 57 minutes on a step that takes 79
seconds. bench.yml and release.yml depend on the same snapshot. tokenfuse#264 (squash-merged as
`b73dd10` on 2026-09-08; on that PR the probe ran for real in the radar job and in
both musl binary jobs, all green) makes the step fail in a minute with the reason
instead of hanging: a probe before each
snapshot-pinned apt line, bounded apt timeouts, the pin untouched; measured in
ubuntu:24.04 containers (outage 7 s, healthy 35 s) and held by three offline
teeth cases. **The minute held for "down", not for "flapping"**: in the second
outage the same evening InRelease answered, later index fetches 503ed, and apt's
per-fetch bounds (Retries=3 x 20 s over dozens of files) ran 27 minutes on the
#265 run (18:45:27 to 19:12:51) before Error-Mode=any ended the step. tokenfuse#266
puts `timeout-minutes: 6` on all three snapshot-pinned steps and drops Retries to 1;
the ceiling fired in GitHub's runner on its first run, tokenfuse PR #266 run
34269627993: `System deps` 19:33:19 to 19:39:31, 6 min 12 s, killed by the step
timeout while the service flapped (it was fully back by 19:36:44). 27 minutes to 6. Falling back to the live archive was then decided: `@yurii 2026-09-08`, "B закриваємо"
(no live-archive fallback; the pin stays), and the vendored-debs and digest-pinned-
container alternatives were judged "трохи зайве" for now. What was taken instead is
exposure reduction: the radar job runs only when crates/radar, ci.yml or the apt
probe changed (a `changes` job and a job-level `if`, so the required check reports
"skipped" rather than never reporting): tokenfuse#265, squash-merged as `30f0248`
on 2026-09-08. On its own PR the `changes` job printed "runs, radar, this workflow or
the apt probe changed"; the skip path is proven by replay only, the first unrelated
PR will show it live. The release-path ceiling also fired on #266's arm64 musl job:
`musl linker` 19:33:30 to 19:39:42, 6 min 12 s, and again on its re-run at
19:48:44 to 19:54:57 while the service was up but slow (10 to 40 s per arm64
index file, sixty-odd files). That is the intended shape now: a degraded snapshot
costs six minutes and a clear message, and the job is re-run when the service
is fast again. #266 did exactly that: re-run at 20:02 once the service served arm64
indexes quickly, green, squash-merged as `3576880` on 2026-09-08. musl was then measured the same day without a
dual-stack network (`/etc/hosts` with one IPv4 and one IPv6 entry; the tracepoint
fires before the syscall, so an unroutable IPv6 probe is still captured):
busybox `wget` on Alpine `connect()`s **each candidate on port 65535** before
the real attempt, glibc (`getent`, `curl`) shows no probe at all
(`evidence/resolvers.json`). So #68's port-53 rule misses musl; the fix is the
443-only rule radar already has: TAIPANBOX/idryx#71 (`destination()` consults
the provider map only on 443; red-first on 65535, 8080 and 80), squash-merged as
`4677225` on 2026-09-08 after a green CI; #70 closed with it.

### 2026-09-09: the sensor moved off the syscall boundary, and both reasons were measured first

Same machine and kernel as the run above (this Mac, Docker Desktop, LinuxKit
**7.0.12 aarch64**, 10 CPUs, privileged container with `tracefs` mounted,
binaries cross-built `GOOS=linux GOARCH=arm64`). Both defects were measured
against the sensor as it stood on `main` at `4677225`, then against the branch,
with the same workload under each. Probes and captures in
`evidence/2026-09-09-*`.

**1. A second thread could choose what the sensor recorded.** The
`sys_enter_connect` tracepoint fires at the syscall boundary, where the
destination is still a pointer into the calling process's memory that the kernel
has not copied yet. `evidence/2026-09-09-toctou-race.c` calls `connect()` in a
loop from a shared sockaddr while another thread flips the port between one with
a listener and one without, so `connect()`'s own return says which port the
kernel actually used. Three runs:

| connections | old sensor | the branch |
|---|---|---|
| 20,000 | 58 recorded a port the kernel did not use | exact |
| 30,000 | 126 | exact |
| 25,000 | 221 | exact |

**2. io_uring was invisible, silently and completely.** `IORING_OP_CONNECT`
copies its address at submission and calls `__sys_connect_file` directly, never
reaching the tracepoint. One io_uring connection and one ordinary one, to
`127.0.0.1:11434` so nothing left the machine
(`evidence/2026-09-09-iouring-connect.c`): the old sensor captured **1** flow
(`2026-09-09-iouring-old.json`), the branch captures **2**
(`2026-09-09-iouring-new.json`), the io_uring one arriving as
`proc:iouring_connect` with the submitting program's own name.

**The fix these two runs measured was then REFUSED, and that is the part worth
reading.** `fentry` on `inet_stream_connect` and `inet_dgram_connect` closed
both defects and was built as TAIPANBOX/idryx#74. A review priced it and it was
closed unmerged, because attaching below the syscall costs more than it buys
today:

- `security_socket_connect` runs BEFORE `sock->ops->connect` in
  `__sys_connect_file` (read at net/socket.c, v6.12 and v7.0), so hooking the
  protocol's connect loses every attempt an LSM denied. For an identity plane,
  the denied attempt is the event most worth having.
- `fentry` on a kernel function needs a BPF trampoline, and arm64 gains one at
  6.4: on 6.1 `bpf_arch_text_poke` pokes only BPF text, `register_fentry`
  returns `-ENOTSUPP` without `tr->fops`, and `DYNAMIC_FTRACE_WITH_DIRECT_CALLS`
  enters arm64's Kconfig at 6.4 (all four read at those tags). The sensor's
  floor would move from 5.8 to 6.4 on arm64, taking the portability that is its
  one advantage over tokenfuse's radar.
- SCTP has its own `sctp_inet_connect`, MPTCP on 6.1 to 6.3 bypasses both
  hooked functions, and one io_uring TCP connect can produce two records because
  `io_connect` re-issues after `EINPROGRESS`. The "2 flows" above was 1 plus 1
  only because nothing was listening on the target port.

**So the two defects are now named limitations rather than silences**
(TAIPANBOX/idryx#75, SECURITY.md), and the redesign is recorded in that
repository's AGENTS.md with what to build (one program on `__sys_connect_file`,
which precedes the LSM hook, is reached by both paths and carries `addrlen`),
the two decisions to take first, and the test matrix. `@decided 2026-09-09`:
redesign once, deliberately, when the sensor goes into a real deployment.

**Wrong once, and worth recording.** The first race probe wrote both port values
to the same field in adjacent statements, `-O2` deleted the first as dead, the
buffer held one value for the whole run and both sensors agreed with ground
truth. A probe that quietly stops racing reports two sensors as identical.

**The committed BPF object did not reproduce from its own source.** Separately,
and found while reading the same code: `internal/ebpfcapture/bpf_bpfel.o` and
`bpf_bpfeb.o` are compiled binaries in git that `//go:embed` puts into every
released binary and published image, and nothing compared them with the C beside
them. CI regenerated `vmlinux.h` from the runner's kernel and ran `go generate`
over the top, overwriting the object before anything looked; the step was even
named "catches connect.c/committed-output drift". Rebuilt in an `ubuntu:24.04`
container with the toolchain that job installs (clang 18.1.3, libbpf 1.3.0, Go
1.27.0) against the committed header, the object committed on 2026-09-08 came
out two instructions shorter, both a redundant `r9 = 0x0` a newer clang proves
unnecessary. Benign, and indistinguishable at the time from a substituted
program. TAIPANBOX/idryx#73 adds `scripts/object-matches-its-source.sh` with a
pinned compiler and four cases in that repository's teeth harness.

**Architecture is not a variable in that comparison**, measured twice: one clang
gave identical bytes on aarch64 and x86_64 containers, and the object generated
here on aarch64 then matched byte for byte on GitHub's own x86_64 runner in the
`ebpf` job of #74.

**What none of this proves.** One kernel, in a container, on one Mac. Never a
fleet, never a cloud host, never x86_64 for the sensor itself, and never against
a real agent. It is not a claim of unevadability either: a host compromised
enough to load kernel code, or to reach the network by a path that never calls
`sock->ops->connect`, is outside all of it. And a kernel that refuses to attach
`fentry` to those two symbols now fails the sensor loudly rather than capturing
part of the traffic; no such kernel has been tried.

## Deployment, NOT proven, with the scope of the gap

| What | Why it is open | Last touched |
|---|---|---|
| `stack-up` on published images | Not migrated. It builds from source by design and says so: it is the local sandbox and needs Rust, Go, Node and Python on the host. `stack-single` migrated on 2026-09-01 (stack-single#27 and #28) and now compiles nothing by default | 2026-09-01 |
| arm64 running on arm64 | The manifest lists carry both architectures and every binary executes on its own runner. No cluster was ever raised on Graviton or any other arm64 host | 2026-09-01 |
| AWS after the GHCR migration | The last three runs were GCP. AWS was last exercised before the image pins | 2026-09-01 |
| Windows, anywhere | Nothing, ever | n/a |

## Traps that bite an operator and that no gate holds

| Trap | Where | Status |
|---|---|---|
| `apply -k` restores `TRAILRYX_TRUST_DOMAIN: set-me.invalid`, and the record plane then refuses every event, which reads as a quiet night | GOTCHAS 90 | Named limitation, not a defect: `cloud/{aws,gcp}/deploy-*.sh` carry `--trust-domain` and their own comment calls the empty default "the loud state and the right default". The base `deploy.sh` has no such flag, and **no gate refuses a finished deploy with the placeholder still set** |
| A delete takes the volume and leaves the secret; `60-harden-neighbours.yaml` cannot be removed at all | GOTCHAS 91 | Measured and named. GOTCHAS 91 says outright "Nothing below is a bug"; three of four are Kubernetes as documented, and only `48` taking the plain scopyx with it is ours |
| A GCP load balancer with a healthy backend that carries nothing | GOTCHAS 69 | Open, and marked Platform: every GCP-side object verified correct |

## The estate's public surface

Do not recall any of it. Run:

```
./scripts/outside-view.py
```

Two findings from its first run, 2026-09-01, that had been guessed wrong before it existed:

- **Every image pinned by a manifest is anonymously pullable.** An earlier claim
  that genaryx had no public image came from asking the registry for `genaryx`;
  the manifests pin `genaryx-console`. The script now derives names from the
  manifests, so that class of error cannot recur.
- **`verdryx` and `vouchryx` are pinned by no manifest at all.** That is a
  different statement from "their image is missing", and the correct one: they
  are not deployed as containers anywhere, which is consistent with running
  inside the console image.

And one gap the script exposes rather than fixes: **21 of 22 repositories
declare no `distribution`**, so where a human installs them has no declared
answer anywhere in the estate. Only Engram declares one (`engdbram`).
