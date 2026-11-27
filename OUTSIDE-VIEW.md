# The estate from outside

**Taken 2026-11-27 20:28 UTC.** Regenerated, never edited by hand:

```
./scripts/outside-view.py --write OUTSIDE-VIEW.md
```

Subjects come from `estate.json`. Image names come from the manifests that pin them. Nothing in this file is recalled.

## Repositories

| repo | vis | stars | forks | issues | open | discussions | latest release | assets |
|---|---|---|---|---|---|---|---|---|
| agent-passport | public | 1 | 1 | True | 1 | True | v1.1.0 | 0 |
| agent-stack-go | public | 1 | 0 | True | 1 | True | v2.0.3 | 10 |
| catalog | public | 0 | 0 | True | 1 | True | none | 0 |
| costcrew | public | 0 | 0 | True | 3 | True | v0.11.0 | 3 |
| engram | public | 6 | 4 | True | 0 | True | v3.1.0 | 7 |
| genaryx | public | 0 | 0 | True | 1 | True | v0.1.0 | 6 |
| heraldyx | public | 0 | 0 | True | 1 | True | v0.10.0 | 3 |
| idryx | public | 1 | 1 | True | 1 | True | v1.4.1 | 10 |
| keyryx | public | 0 | 0 | True | 1 | True | v0.2.0 | 3 |
| mockryx | public | 2 | 1 | True | 2 | True | v0.5.1 | 10 |
| netryx | public | 0 | 0 | True | 0 | False | none | 0 |
| qryx | public | 2 | 1 | True | 1 | True | v1.2.1 | 10 |
| scopyx | public | 0 | 0 | True | 1 | True | v1.3.1 | 3 |
| stack-k8s | public | 0 | 0 | True | 2 | True | v1.19.0 | 4 |
| stack-single | public | 0 | 0 | True | 1 | True | v1.15.0 | 4 |
| stack-up | public | 0 | 0 | True | 1 | True | none | 0 |
| taipan | public | 0 | 0 | True | 0 | True | none | 0 |
| terraform-provider-taipan | public | 1 | 0 | True | 1 | True | v0.2.0 | 19 |
| tokenfuse | public | 1 | 1 | True | 1 | True | v1.27.0 | 17 |
| tokenfuse-mobile | public | 0 | 0 | True | 1 | False | none | 0 |
| trailryx | public | 0 | 0 | True | 1 | True | v1.7.0 | 19 |
| typryx | public | 0 | 0 | True | 1 | True | v0.6.1 | 3 |
| typryx-evalset | public | 0 | 0 | True | 0 | False | none | 0 |
| verdryx | public | 1 | 1 | True | 1 | True | v0.4.0 | 0 |
| vouchryx | public | 0 | 0 | True | 1 | True | v0.9.0 | 3 |
| wardryx | public | 1 | 1 | True | 1 | True | v2.8.0 | 3 |

**Not measured** (and therefore not clean):
- architecture: PRIVATE by decision (2026-09-09): one file per service saying how it is built and why, with the decisions behind it. Not for outsiders. CI cannot clone it, so C18 is measured only in a local run.
- bank-in-a-box: PRIVATE remote (git@github.com:TAIPANBOX/bank-in-a-box.git, since 2026-08-28) and no CI. CI cannot clone it, so anything it contributes is measured only in a local run.

## Private by decision

Repositories `estate.json` records as private on purpose (`private_remote`). A flip to public is silent everywhere else, so it is measured here and fails the run.

- architecture (`TAIPANBOX/architecture`): private, as decided
- bank-in-a-box (`TAIPANBOX/bank-in-a-box`): private, as decided

## Container images, as a stranger's docker sees them

Names are taken from every `ghcr.io/` reference pinned in the estate's own manifests, so this list cannot drift from what actually gets deployed. The pull is anonymous: no login, no token.

| image | pinned by | anonymous pull |
|---|---|---|
| `agent-conform` | stack-k8s:40-routines-and-secrets.yaml, stack-single:compose.yaml | yes, 24 tag(s), latest version v2.0.3 |
| `costcrew` | stack-k8s:49-costcrew.yaml, stack-single:compose.yaml | yes, 33 tag(s), latest version v0.11.0 |
| `genaryx` | stack-k8s:10-planes.yaml, stack-k8s:20-console.yaml, stack-k8s:40-routines-and-secrets.yaml | yes, 4 tag(s), latest version v0.1.0 |
| `heraldyx` | stack-k8s:45-heraldyx.yaml, stack-k8s:compose.yaml, stack-k8s:heraldyx-findings-patch.yaml | yes, 56 tag(s), latest version v0.10.0 |
| `idryx` | stack-k8s:10-planes.yaml, stack-k8s:40-routines-and-secrets.yaml, stack-single:compose.yaml | yes, 36 tag(s), latest version v1.4.1 |
| `keyryx` | stack-k8s:59-keyryx.yaml, stack-single:compose.yaml | yes, 27 tag(s), latest version v0.2.0 |
| `mockryx` | stack-k8s:40-routines-and-secrets.yaml, stack-k8s:45-heraldyx.yaml, stack-k8s:52-tokenfuse-mcp-broker.yaml | yes, 32 tag(s), latest version v0.5.1 |
| `qryx` | stack-k8s:40-routines-and-secrets.yaml | yes, 23 tag(s), latest version v1.2.1 |
| `scopyx` | stack-k8s:47-scopyx.yaml, stack-k8s:48-scopyx-browser.yaml, stack-single:compose.yaml | yes, 62 tag(s), latest version v1.3.1 |
| `stack-caddy` | stack-single:compose.yaml | yes, 165 tag(s), latest version v1.19.0 |
| `stack-wg` | stack-single:compose.yaml | yes, 165 tag(s), latest version v1.19.0 |
| `tokenfuse` | stack-k8s:10-planes.yaml, stack-k8s:52-tokenfuse-mcp-broker.yaml, stack-k8s:broker-base-v1.18.0.yaml | yes, 336 tag(s), latest version v1.27.0 |
| `tokenfuse-control-plane` | stack-k8s:10-planes.yaml, stack-single:compose.yaml, tokenfuse:docker-compose.yml | yes, 167 tag(s), latest version v1.27.0 |
| `tokenfuse-dashboard` | tokenfuse:docker-compose.yml | yes, 163 tag(s), latest version v1.27.0 |
| `trailryx-node` | stack-k8s:40-routines-and-secrets.yaml, stack-single:compose.yaml | yes, 26 tag(s), latest version v1.7.0 |
| `typryx` | stack-k8s:51-typryx.yaml, stack-k8s:56-typryx-wardryx-proxy.yaml, stack-single:compose.yaml | yes, 31 tag(s), latest version v0.6.1 |
| `vouchryx` | stack-k8s:54-delegation.yaml, stack-k8s:vouchryx.yaml, stack-single:compose.yaml | yes, 35 tag(s), latest version v0.9.0 |
| `wardryx` | stack-k8s:10-planes.yaml, stack-k8s:wardryx-patch.yaml, stack-k8s:wardryx-unpatch.yaml | yes, 97 tag(s), latest version v2.8.0 |

## Where each repository says it is published

`distribution` in a repository's own `components.json`. A repository with none has not declared where a human installs it, and this script will not invent an answer.

- **agent-stack-go**: `Go module github.com/TAIPANBOX/agent-stack-go/v2 by tag; agent-conform archives with SHA256SUMS on each GitHub Release; the agent-conform image ghcr.io/taipanbox/agent-conform:<tag> (amd64, arm64, signed, attested) on each v* tag`
- **costcrew**: `ghcr.io/taipanbox/costcrew`
- **engram**: `engdbram`
- **genaryx**: `ghcr.io/taipanbox/genaryx; built, signed and released by this repository's .github/workflows/release.yml on a v* tag (the console with its four tools and two engines). First release v0.1.0 (sha256:4030bc819e7df40c2a307e68f33519476d0858570bbdccb9326fd5fad256d2ee); the stacks run ghcr.io/taipanbox/genaryx-console, composed by stack-k8s, until their next release pins this image`
- **heraldyx**: `ghcr.io/taipanbox/heraldyx`
- **idryx**: `ghcr.io/taipanbox/idryx; per-target archives with SHA256SUMS on each GitHub Release`
- **keyryx**: `published as ghcr.io/taipanbox/keyryx: v0.1.0 (2026-10-18), v0.1.1 (2026-10-19), v0.1.2 (2026-10-19), v0.1.3 (2026-10-26) and v0.1.4 (2026-11-07, the latest), by .github/workflows/release.yml on each v* tag push, for linux/amd64 and linux/arm64, with an SBOM and a build-provenance attestation attached. v0.1.1, v0.1.2, v0.1.3 and v0.1.4 carry a cosign signature in the legacy cosign format; v0.1.0 carries none`
- **mockryx**: `ghcr.io/taipanbox/mockryx; per-target archives with SHA256SUMS on each GitHub Release`
- **qryx**: `ghcr.io/taipanbox/qryx; per-target archives with SHA256SUMS on each GitHub Release`
- **scopyx**: `ghcr.io/taipanbox/scopyx, per tag also scopyx:<tag>-chromium`
- **stack-k8s**: `manifests by tag, applied with kubectl or the install script, and a signed release tree for a piped deploy (release.yml); images ghcr.io/taipanbox/stack-caddy and ghcr.io/taipanbox/stack-wg, built for amd64 and arm64 by tunnel-images.yml and merged into one tag. The console image is genaryx's own release (ghcr.io/taipanbox/genaryx) since 1.19.0, pulled by digest`
- **stack-single**: `git clone and ./install.sh on one machine; pins released images of every plane`
- **stack-up**: `git clone and ./up.sh (./down.sh, ./routines.sh) on one machine; builds every plane from source at the release tag and commit the pin table in up.sh names (invariant 29); --from-main builds sibling or main checkouts instead, and that is not a release`
- **taipan**: `not distributed: no build or test CI (its one workflow runs only the secret scan), no tag, no release; built from source with cargo build on the operator's own machine`
- **terraform-provider-taipan**: `registry.terraform.io/TAIPANBOX/taipan (Terraform Registry); GPG-signed archives on each GitHub Release`
- **trailryx**: `ghcr.io/taipanbox/trailryx (trailryx-ingest, the OTLP receiver) and ghcr.io/taipanbox/trailryx-node (trailryx-node + trailryx-verify, the record plane, since v0.1.2); per-target trailryx-verify, trailryx-ingest and, on the two linux-musl targets, trailryx-node binaries with a merged SHA256SUMS on each GitHub Release`
- **typryx**: `ghcr.io/taipanbox/typryx, per tag (v0.1.0 first, 2026-09-25; v0.2.0, 2026-09-26; v0.3.0, 2026-09-30; v0.4.0, 2026-10-04; v0.4.1, 2026-10-14; v0.5.0, 2026-10-19; v0.5.1, 2026-10-26; v0.6.0, 2026-11-06; v0.6.1, 2026-11-12)`
- **verdryx**: `not published: installed from the repository with pip (git+https); no PyPI package yet`
- **vouchryx**: `ghcr.io/taipanbox/vouchryx, published by .github/workflows/release.yml on a v* tag push (linux/amd64 and linux/arm64, signed keyless with cosign, SBOM and build-provenance attestation attached); first tag v0.1.0, the delegation token issuer, agent credential issuer and revocation list the stack launchers run`
- **wardryx**: `ghcr.io/taipanbox/wardryx`

**Undeclared (8 of 28):** agent-passport, architecture, bank-in-a-box, catalog, netryx, tokenfuse, tokenfuse-mobile, typryx-evalset

