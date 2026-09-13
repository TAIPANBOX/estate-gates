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
| The OpenAI door (`/v1/chat/completions`, tokenfuse main at `a83f747`, built locally, unreleased) in `enforce` mode in front of OpenRouter: call 1 served at `x-fuse-price: fallback`, call 2 refused `402 budget_exceeded` in the OpenAI error shape, three `breaker_tripped` events chained | 2026-09-12 | this Mac, native binary, `cargo build --release` 2 min 43 s | `go-to-market-2026-09/evidence/1.0/r3-openrouter-openai-door-2026-09-12/` | One door, one provider, one run, `openai/gpt-4o-mini`, about USD 0.00006. Finding: the price book does not know OpenRouter's vendor-prefixed ids, so the call was fallback-priced at about 100x; a first attempt with a real-price budget was refused before any call, which is the documented estimate-then-settle behaviour. Not streaming, not the released image |

| The first tag through the wave-1 release mechanics: `tokenfuse` `v0.5.0` (`da324a9`), release run 34724668614 green on every job. From a machine that built nothing: `sha256sum -c` OK on a downloaded binary against the released `SHA256SUMS`; `gh attestation verify tokenfuse-cloud-aarch64-apple-darwin -R TAIPANBOX/tokenfuse` and `gh attestation verify oci://ghcr.io/taipanbox/tokenfuse:v0.5.0 -R TAIPANBOX/tokenfuse` both returned one SLSA provenance v1 statement (16 subjects for the release assets; the image by manifest-list digest) signed by `.github/workflows/release.yml@refs/tags/v0.5.0` through `token.actions.githubusercontent.com`. The release page carries `SHA256SUMS.sigstore.json` (Sigstore bundle v0.3), `sbom.spdx.json` (SPDX-2.3, 1106 packages), `sbom.cyclonedx.json` (1.7, 1116 components) and `provenance.intoto.jsonl`. The registry carries `v0.5.0` and `v0.5.0-cluster` and no new moving tag. | 2026-09-13 | GitHub Actions (the run), this Mac (the verification, gh 2.100.0) | `gh run view 34724668614 --repo TAIPANBOX/tokenfuse`; the release page; scratchpad `wave1/v050/` for the downloaded files | The `cosign verify-blob` half of the README's recipe was NOT run here: cosign is not installed on this machine, so the Sigstore bundle on `SHA256SUMS` is present and unverified from outside the runner; `gh attestation verify` covers the same file through the provenance statement. The July `latest` and `cluster` tags were deleted on 2026-09-13 on the owner's word (four package versions from 2026-07-15, `sha-8756b8b`/`cluster-8756b8b`, each carrying only its moving tag and its own sha tag; `gh api -X DELETE user/packages/container/<image>/versions/<id>`); @measured `curl .../v2/taipanbox/<image>/tags/list` 2026-09-13 afterwards: no `latest` and no bare `cluster` on any of the three images, `v0.5.0` present, and `docker pull ghcr.io/taipanbox/tokenfuse` answers `not found`, which is route A working. |

## The 1.0 proving run, proven (RELEASE-1.0-PLAN-2026-09-12 section 5.3)

One row per scenario group per rig. R0 is this Mac; the four R1 scenarios run
here ahead of R1 count for the behaviour, not for R1, until a Linux box under
systemd repeats them. `SUMMARY.md` in the evidence directory carries the seven
findings of the run.

| What | When | On what | Artifact | Scope |
|---|---|---|---|---|
| INS-1: the README `docker run` of `tokenfuse:v0.5.0` on a machine that had only v0.4.4, `/healthz` 200, a 0.02 USD run refused on its third call with `402 budget_exceeded` (spent 0.021) | 2026-09-12 | this Mac, Docker Desktop, the image pulled by tag (linux/arm64, digest `dcf35d5…`) | `go-to-market-2026-09/evidence/1.0/r0-mac-2026-09-13/ins-1-pull.log`, `ins-1-run.log` | one door, the stub upstream. Finding: the container's `--version` prints `tokenfuse  ()` (tokenfuse #275, open) |
| INS-4 cold: `stack-up --with-delegation --with-finops` from an empty workspace, empty `CARGO_HOME`/`GOMODCACHE`/`GOCACHE`/npm cache, fresh `TAIPAN_HOME`: 12 repos cloned, 15 binaries built (399 crates downloaded, 353 compiled, 100 Go modules), **325 s** to every plane answering, clean stop, exit 0 | 2026-09-13 | this Mac, Apple Silicon, stack-up `8700c3b` | `go-to-market-2026-09/evidence/1.0/r0-mac-2026-09-13/ins-4-cold-stack-up.log` and `.up` | tools ON this time (2026-09-01 measured 221 s with `--no-tools`). Warm only in the toolchains themselves (rustup, Go, node, python3). The warm run the same night (`ins-4-stack-up.log`) ended when FAIL-2 killed wardryx: the launcher stops the whole stand when one plane exits, by design |
| RUN-2: the wrong door for the process's wire is refused `400 wire_mismatch` before anything is reserved; the right door on the same run still has the full budget | 2026-09-12 | this Mac, the v0.5.0 container from INS-1 | `go-to-market-2026-09/evidence/1.0/r0-mac-2026-09-13/run-2.log` | docs/26's claim, one process, one run |
| RUN-4: `bank-in-a-box` night incident, the seven-check scoreboard **7/7 PASS** (402 within budget, breaker chain intact, events valid each against its own schema version, Idryx `runaway_agent` HIGH, Engram `why()` provenance, Qryx quantum at-risk, outcomes report) and its self-test still trips all 8 broken inputs; `offline-only` OK | 2026-09-12 | this Mac, siblings tokenfuse `d4e9ddd`, idryx `bfd7c7b`, qryx `25cf2a5`, engram `f16b59a`, bank-in-a-box `3eaf073` + PR #4 | `go-to-market-2026-09/evidence/1.0/r0-mac-2026-09-13/run-4-scoreboard.log`, `run-4-events.ndjson` | the first attempt could not start the stand's gateway (no `TOKENFUSE_ALLOW_STUB`, a precondition since 2026-08-05) and the second failed the schema check (pinned to v0.1): both fixed in bank-in-a-box #4, open |
| RUN-5 (R1 scenario, ahead): hierarchical runs; with wardryx enforcement on, a call without `x-fuse-agent-id` is `400 identity_required`; with it, the parent (0.02) serves itself and child a, and child b is `402` with the parent spent 0.021 | 2026-09-13 | this Mac, stack-up's gateway (main, 0.0.1-dev), stub upstream | `go-to-market-2026-09/evidence/1.0/r0-mac-2026-09-13/run-5-hierarchy.log` | one parent, two children; the R1 run is still owed |
| RUN-6 (R1 scenario, ahead): the same over-budget run in shadow (all four calls forwarded, ledger at 210 %) and in enforce (402 on call 3, `breaker_tripped` on the bus, trace `budget_exceeded`) | 2026-09-13 | this Mac, `~/.taipan/bin/tokenfuse-gateway` (main, 0.0.1-dev), stub upstream, wardryx up | `go-to-market-2026-09/evidence/1.0/r0-mac-2026-09-13/run-6-shadow-then-enforce.log`, `run-6-run.sh` | **finding**: shadow records no would-be refusal for the run budget (no `x-fuse-would-block`, no event, trace `allow`); README line 381 promises it does. T3, open, fix proposed in SUMMARY.md |
| POL-3 (R1 scenario, ahead): scopyx's gates in order, address rule `deny_address`, allowed origin fetched, denied origin `deny_policy`, an allowed origin redirecting into a denied one refused on the target host, robots `deny_robots` (github.com `/search$`), PDP killed `deny_policy_unreachable`; each on the bus as `web_blocked` high | 2026-09-13 | this Mac, `~/.taipan/bin/scopyx` and `wardryx` on private ports with `policy-r0.yaml` | `go-to-market-2026-09/evidence/1.0/r0-mac-2026-09-13/pol-3-scopyx-gates.log`, `pol-3-run.sh`, `stand.sh` | five gates, one agent identity, one policy |
| INT-1: nine framework recipes (LangChain, OpenAI Agents SDK, PydanticAI, CrewAI, AutoGen, Semantic Kernel, LiteLLM, Haystack, Claude Code documented) against Ollama `qwen2.5:3b` through both doors of the v0.5.0 image: **12 door runs, 12 refusals** with each framework's own exception; CrewAI's `extra_headers` reaches the gateway through LiteLLM | 2026-09-13 | this Mac, Python 3.14.7 (CrewAI in `python:3.13-slim`), two v0.5.0 containers | `go-to-market-2026-09/evidence/1.0/r0-mac-2026-09-13/int-1-recipes.log`, `int-1-crewai.log`; the recipes are tokenfuse #276 | prices are the fallback book (`x-fuse-price: fallback`); the CI matrix is not run (the stub refuses the OpenAI wire by design) |
| INT-3: an MCP client on scopyx `browse` (allowed fetched, denied refused) and on the tokenfuse mcp-broker with wardryx `decide()` on `tools/call`: `shell_exec` refused for the mockryx identity with wardryx's reason (JSON-RPC -32004) and provably absent from the upstream's log, `read_clock` forwarded, a call with no identity refused | 2026-09-13 | this Mac, the broker from `~/.taipan/bin/tokenfuse-gateway mcp-broker`, a 30-line echo MCP upstream | `go-to-market-2026-09/evidence/1.0/r0-mac-2026-09-13/int-3-mcp-layer.log`, `int-3-run.sh`, `echo_mcp.py` | the client was JSON-RPC by hand, not Claude Code or Cursor. Finding: broker and scopyx do not chain (no upstream credential) |
| SUP-1: the README's own verify commands from a machine that built nothing: `cosign verify-blob` OK on `SHA256SUMS`, `sha256sum -c` OK, `gh attestation verify` OK on the asset and on four images, one flipped hex digit fails | 2026-09-12 | this Mac, cosign v3.1.3 in a container, gh 2.100.0 | `go-to-market-2026-09/evidence/1.0/r0-mac-2026-09-13/sup-1.log` | tokenfuse v0.5.0 only; the other eleven repos' mechanics are proven by their first tag, not yet cut |
| FAIL-2 (R1 scenario, ahead): wardryx killed under a running gateway and scopyx: tokenfuse forwards (200, `x-fuse-wardryx: allow`) and records `dependency_failed` high `allowed_ungoverned` `failmode=Open applied`, `/v1/policy-plane` `falling_back: true`; scopyx refuses `deny_policy_unreachable` and records `web_blocked` high | 2026-09-13 | this Mac, the three planes started by `fail-2-run.sh` outside stack-up (stack-up itself stops the stand when a plane dies) | `go-to-market-2026-09/evidence/1.0/r0-mac-2026-09-13/fail-2-pdp-down.log`, `fail-2-run.sh` | within the gateway's 3 s decision cache the cached allow is reused and no outage is noticed; the run shows both sides of the TTL |
| INS-2 (R1a): `stack-single` by its README one-liner on a fresh GCP `e2-standard-2`, installer md5 checked against main: **112 s, exit 0, 21 ok, 0 fail**, 8 images pulled, nothing built; the same installer again on the same box: 33 s, 21 ok, no container recreated, 15 volumes unchanged, .env and compose.yaml untouched; a second fresh box: 116 s, 21 ok | 2026-09-13 | GCP europe-west3-a, Ubuntu 26.04.1, Docker 29.1.3, stack-single `87a77ac`; both boxes destroyed the same hour | `go-to-market-2026-09/evidence/1.0/r1-gcp-2026-09-13/ins-2-run1-x86.log`, `ins-2-run2-x86-rerun.log`, `ins-2-run3-x86-fresh-box.log`, `logs/` (full install logs, passwords redacted) | pins as on main that day (tokenfuse v0.4.4, wardryx v0.1.0, idryx v0.3.0, console v0.1.2). Finding: the gateway exported no events and three profiles could not write their volumes (stack-single #41), invisible to all 21 checks |
| INS-3 (R1b): the same install on arm64, GCP `t2a-standard-2`: **83 s, exit 0, 21 ok**; every one of the 9 running images resolved `linux/arm64`, same manifest-list digests as x86 | 2026-09-13 | GCP europe-west4-a, Ubuntu 26.04.1 arm64; destroyed after 22 min | `go-to-market-2026-09/evidence/1.0/r1-gcp-2026-09-13/ins-3-arm64.log`, `logs/r1b-install-1.log` | closes "arm64 running on arm64" below at the cheapest shape; no cluster on arm64 yet |
| INS-7 (R1a): the README install blocks and first commands of qryx, idryx and trailryx run literally on the clean box: release tarballs and binaries downloaded and `sha256sum -c` OK, `qryx version` v0.3.1, `idryx version` v0.3.1, `idryx detect` on the day's real bus raised `runaway_agent`, trailryx's day sealed under `--trust-domain taipanbox.dev` (4 lines, 7 records), packed and **VERIFIED** by the v0.1.2 release verifier | 2026-09-13 | the R1a box | `go-to-market-2026-09/evidence/1.0/r1-gcp-2026-09-13/ins-7-readme-commands-r1.log` | two trailryx README lines assume a host binary (the image has no entrypoint) and omit `--trust-domain`; the wrong-domain run refuses loudly and moves no cursor (finding 6 in SUMMARY.md) |
| UPG-1 and UPG-5 (R1a): the stand's Parquet trace written by tokenfuse 0.4.4, read by 0.5.0 after moving `TOKENFUSE_IMAGE` in .env: `outcomes` and `sql` identical to the microdollar, the columns the old writer lacked read as empty; `docker compose up -d` converged in 7 s recreating only the gateway, volumes and policy-db untouched, 21 checks on the upgraded stand | 2026-09-13 | the R1a box | `go-to-market-2026-09/evidence/1.0/r1-gcp-2026-09-13/upg-1-5-r1.log` | 8 calls of trace, not a day; the v0.5.0 image prints `tokenfuse  ()` for `--version` (tokenfuse #275 fixes the next tag) |
| UPG-3 (R1a): records sealed by the `trailryx-node:v0.1.2` image, verified by `trailryx-verify` built from main `8f84c4c` on the box: **VERIFIED**, completeness proof Full when the main node reads the 0.1.2 data dir | 2026-09-13 | the R1a box, rustup stable, 44 s build | `go-to-market-2026-09/evidence/1.0/r1-gcp-2026-09-13/upg-3-r1.log` | one pack of 7 records |
| RUN-5, RUN-6, POL-3, FAIL-2 on R1a (the R1 runs of the four scenarios R0 ran ahead): RUN-5 child b `402` on the parent's budget; RUN-6 enforce 402 on call 3 with `breaker_tripped` on the bus, shadow forwards with no would-block signal (the R0 finding on the released v0.5.0); POL-3 five gates on the stand's scopyx v0.1.2 with wardryx v0.1.0; FAIL-2 with the stand's `TOKENFUSE_WARDRYX_FAILMODE: closed`: **403 wardryx_denied** and `dependency_failed` high, scopyx `deny_policy_unreachable`, both recover | 2026-09-13 | the R1a box, stack-single's compose with a run override (stub upstream, events path) | `go-to-market-2026-09/evidence/1.0/r1-gcp-2026-09-13/run-5-6-r1.log`, `pol-3-r1.log`, `fail-2-r1.log` | the events path had to be supplied by the override (finding 1); the stand's gateway is fail-closed by configuration where stack-up's default was fail-open, so both failmodes are on record |
| POL-5 (R1a): qryx v0.3.1 `image` on the stand's three images (350/146/146 findings), `bin` on four release binaries, `tls` on the console by name (ECDSA-256 quantum-vulnerable, correct), `scan --format cbom` of tokenfuse source **VALID CycloneDX 1.6** (jsonschema 4.19.2 against the 1.6 schema), signed ed25519 evidence **VERIFIED** and a one-number tamper refused with "digest mismatch" | 2026-09-13 | the R1a box | `go-to-market-2026-09/evidence/1.0/r1-gcp-2026-09-13/pol-5-r1.log` | **finding**: `image --format cbom` yields 9 schema errors (primitives `encryption`, `key-exchange`; asset type `library`), see `finding-qryx-cbom-not-cyclonedx-1.6.log`; fix owed in qryx |
| REC-3 (R1a): `trailryx-demo --runs 2` from main: 4 keys destroyed over 4 payloads, the same pack VERIFIED again byte for byte, payloads unreachable in storage; the kept pack VERIFIED by the v0.1.2 release verifier | 2026-09-13 | the R1a box | `go-to-market-2026-09/evidence/1.0/r1-gcp-2026-09-13/rec-3-r1.log`, `logs/rec-3-demo-full.out` | erasure is a library and the demo path; `trailryx-node` has no erase command (named gap) |
| INT-5 (R1a), the API half: inside the stand's console container, Engram 2.4.1 episode, fact with source, `why()` with a non-empty chain, recall | 2026-09-13 | the R1a box | `go-to-market-2026-09/evidence/1.0/r1-gcp-2026-09-13/int-5-r1.log` | **finding**: the console half fails, `engram-mcp` in the console image dies for want of the `mcp` extra and the descriptor has no `services.engram`; Engram's first use fetched its embedding model from the HF Hub |
| SUP-3 (R1a): tcpdump of every outbound SYN and DNS query for the scenario set, read name by name: image registries, GitHub releases, the scenarios' own targets, apt and rustup (the operator's), the GCE guest agent (the image's), and **api.ipify.org asked by install.sh on every run**; nothing else | 2026-09-13 | the R1a box, two captures (a 4 min gap where the first died with its SSH session) | `go-to-market-2026-09/evidence/1.0/r1-gcp-2026-09-13/sup-3-egress-r1.log`, `capture/*.pcap`, `sup3-dns.txt`, `sup3-syns.txt` | the HF Hub fetch of INT-5 fell in the gap and is in `int-5-r1.log` only |
| FAIL-5 (R1a): the record plane on a 64 KiB tmpfs: `journal: io: No space left on device`, exit 2, no cursor written, the store reads back 0 records; the same input on a real disk seals 400; identical under v0.1.2 and main | 2026-09-13 | the R1a box | `go-to-market-2026-09/evidence/1.0/r1-gcp-2026-09-13/fail-5-r1.log` | one failure mode (ENOSPC at seal time), not a full disk mid-segment |

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
| arm64 running on arm64, as a cluster | `stack-single` ran on a GCP `t2a-standard-2` on 2026-09-13 (INS-3 above, every image linux/arm64); no CLUSTER has been raised on Graviton or any other arm64 host | 2026-09-13 |
| AWS after the GHCR migration | The last three runs were GCP. AWS was last exercised before the image pins | 2026-09-01 |
| Windows, anywhere | Nothing, ever | n/a |
| INT-2: Claude Code through the gateway | The standalone `claude` CLI on the Mac is not logged in (the desktop app's session does not reach a CLI started from a shell); `go-to-market-2026-09/evidence/1.0/r0-mac-2026-09-13/int-2-run.sh` is the one command once it is | 2026-09-13 |
| SUP-4: Scorecard on the 1.0 candidates | Still 404 for every repository after the Sunday 07:41Z run, and now known why: every upload is refused as an "imposter commit" because 21 workflows pin `ossf/scorecard-action` to the annotated tag object of v2.4.4 (55891bb) rather than its commit (2d11466); same for `github/codeql-action`. Fix: estate-gates #66 (C21) and twenty one-line PRs `ci/pin-actions-to-commits`. Measurable after they merge and the next push or Sunday run. `evidence/1.0/r0-mac-2026-09-13/sup-4-scorecard-sunday.log` | 2026-09-13 |
| The recipes' CI matrix (INT-1's second half) | The offline stub refuses to start on the OpenAI wire by design, so a CI job needs a real OpenAI-shaped upstream; tokenfuse #276 ships the recipes without it | 2026-09-13 |
| R1: RUN-7, POL-6, REC-4 | RUN-7 needs vouchryx, which stack-single does not carry (a stack-up build on the 2 vCPU box was not attempted); POL-6's eBPF radar is not a released asset; REC-4 needs SMTP to a mailbox of his | 2026-09-13 |
| R2 and R3 of the 1.0 plan | Nothing on a cluster or a paid provider yet | 2026-09-13 |

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
