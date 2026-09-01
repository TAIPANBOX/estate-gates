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

## Deployment, NOT proven, with the scope of the gap

| What | Why it is open | Last touched |
|---|---|---|
| The 2026-08-31 `WARDRYX_DSN` to `WARDRYX_DB` change through a full `stack-single` bring-up | Proven narrowly with a real Postgres and a real binary, never through `docker compose up` or `install.sh` | 2026-08-31 |
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
