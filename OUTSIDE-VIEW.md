# The estate from outside

**Taken 2026-09-01 19:07 UTC.** Regenerated, never edited by hand:

```
./scripts/outside-view.py --write OUTSIDE-VIEW.md
```

Subjects come from `estate.json`. Image names come from the manifests that pin them. Nothing in this file is recalled.

## Repositories

| repo | vis | stars | forks | issues | open | discussions | latest release | assets |
|---|---|---|---|---|---|---|---|---|
| agent-passport | public | 1 | 1 | True | 0 | True | none | 0 |
| agent-stack-go | public | 1 | 0 | True | 0 | True | v0.8.0 | 6 |
| catalog | public | 0 | 0 | True | 0 | True | none | 0 |
| costcrew | public | 0 | 0 | True | 0 | True | none | 0 |
| engram | public | 2 | 1 | True | 0 | True | v2.4.1 | 0 |
| genaryx | public | 1 | 0 | True | 0 | True | none | 0 |
| heraldyx | public | 0 | 0 | True | 0 | True | none | 0 |
| idryx | public | 1 | 1 | True | 0 | True | v0.3.1 | 6 |
| mockryx | public | 2 | 1 | True | 1 | True | v0.2.1 | 6 |
| qryx | public | 1 | 1 | True | 0 | True | v0.3.1 | 6 |
| scopyx | public | 0 | 0 | True | 0 | True | none | 0 |
| stack-k8s | public | 0 | 0 | True | 0 | True | none | 0 |
| stack-single | public | 0 | 0 | True | 0 | True | none | 0 |
| stack-up | public | 0 | 0 | True | 0 | True | none | 0 |
| terraform-provider-taipan | public | 1 | 0 | True | 0 | True | v0.1.1 | 16 |
| tokenfuse | public | 1 | 1 | True | 0 | True | v0.4.0 | 0 |
| trailryx | public | 0 | 0 | True | 0 | True | v0.1.2 | 15 |
| verdryx | public | 2 | 1 | True | 0 | True | none | 0 |
| vouchryx | public | 0 | 0 | True | 0 | True | none | 0 |
| wardryx | public | 2 | 1 | True | 0 | True | none | 0 |

**Not measured** (and therefore not clean):
- bank-in-a-box: Deliberately has no remote at all (its CLAUDE.md forbids adding one). Local only, by decision.
- taipan: PRIVATE repository with no public remote. CI cannot clone it, so anything it contributes is measured only in a local run.

## Container images, as a stranger's docker sees them

Names are taken from every `ghcr.io/` reference pinned in the estate's own manifests, so this list cannot drift from what actually gets deployed. The pull is anonymous: no login, no token.

| image | pinned by | anonymous pull |
|---|---|---|
| `costcrew` | stack-k8s:49-costcrew.yaml | yes, 1 tag(s), latest v0.1.0 |
| `genaryx-console` | stack-k8s:20-console.yaml, stack-k8s:40-routines-and-secrets.yaml, stack-single:compose.yaml | yes, 2 tag(s), latest v0.1.1 |
| `heraldyx` | stack-k8s:45-heraldyx.yaml, stack-single:compose.yaml | yes, 8 tag(s), latest sha-0253656 |
| `idryx` | stack-k8s:10-planes.yaml, stack-k8s:40-routines-and-secrets.yaml, stack-single:compose.yaml | yes, 4 tag(s), latest sha-379a78d |
| `mockryx` | stack-k8s:40-routines-and-secrets.yaml | yes, 8 tag(s), latest sha-1c615c4 |
| `qryx` | stack-k8s:40-routines-and-secrets.yaml | yes, 4 tag(s), latest sha-48946ed |
| `scopyx` | stack-k8s:47-scopyx.yaml, stack-k8s:48-scopyx-browser.yaml, stack-single:compose.yaml | yes, 10 tag(s), latest sha-867cf47-chromium |
| `stack-caddy` | stack-single:compose.yaml | yes, 1 tag(s), latest v0.1.2 |
| `stack-wg` | stack-single:compose.yaml | yes, 1 tag(s), latest v0.1.2 |
| `tokenfuse` | stack-k8s:10-planes.yaml, stack-single:compose.yaml, tokenfuse:docker-compose.yml | yes, 32 tag(s), latest sha-93103e9 |
| `tokenfuse-control-plane` | stack-k8s:10-planes.yaml, stack-single:compose.yaml, tokenfuse:docker-compose.yml | yes, 15 tag(s), latest sha-93103e9 |
| `tokenfuse-dashboard` | tokenfuse:docker-compose.yml | yes, 11 tag(s), latest sha-93103e9 |
| `trailryx-node` | stack-k8s:40-routines-and-secrets.yaml, stack-single:compose.yaml | yes, 1 tag(s), latest v0.1.2 |
| `wardryx` | stack-k8s:10-planes.yaml, stack-single:compose.yaml | yes, 2 tag(s), latest sha-a725f45 |

## Where each repository says it is published

`distribution` in a repository's own `components.json`. A repository with none has not declared where a human installs it, and this script will not invent an answer.

- **engram**: `engdbram`

**Undeclared (21 of 22):** agent-passport, agent-stack-go, bank-in-a-box, catalog, costcrew, genaryx, heraldyx, idryx, mockryx, qryx, scopyx, stack-k8s, stack-single, stack-up, taipan, terraform-provider-taipan, tokenfuse, trailryx, verdryx, vouchryx, wardryx

