# The same pipes in the rest of the estate, 2026-11-06

`../gate-loop.sh` on forge, 4 cores, bash 5.2.37, GNU grep 3.11, beside six busy loops. `red-<repo>` is the tree at the commit below, `green-<repo>` the tree that was pushed, the same gates, the same load. `scopyx-loops.sh` and `others-loops.sh` are the runs.

| Repository | Tree before | Gates looped | Healthy tree, before | After |
|---|---|---|---|---|
| stack-up | `e5bbf42` | 9 | 5 of 900, all `typed-mode.sh` | 0 of 900 |
| scopyx | `6103bc4` | 5 | 2 of 500, both `no-warm-context.sh` | 0 of 500 |
| tokenfuse | `16cc335` | 3 | 5 of 300, `taint-comes-from-the-act.sh` 4, `upstream-key-is-never-forwarded.sh` 1 | 0 of 300 |
| genaryx | `dc32da1` | 1 | 0 of 100 | 0 of 100 |
| heraldyx | `f1a5438` | 1 | 0 of 100 | 0 of 100 |
| qryx | `f46af87` | 1 | 0 of 100 | 0 of 100 |
| catalog | `4b2a242` | 1 | 0 of 100 | 0 of 100 |
| trailryx | `7cf4795` | 1 | 0 of 20 | 0 of 20 |
| idryx | `d8ab1e6` | 1 | 0 of 20 | 0 of 20 |

In all, 12 of 2140 before and 0 of 2140 after.

The other direction, `red-fault-scopyx` and `green-fault-scopyx`: `var _ = "cookiejar"` planted at the top of `internal/backend/chromium.go`, which `scripts/no-warm-context.sh` exists to refuse. On the old tree it was caught 81 of 100 runs, so 19 runs reported a clean tree with the fault in it. On the fixed tree it was caught 100 of 100.

`gate-red-<repo>.txt` is `scripts/no-reader-leaves-a-pipe-early.sh` run over each old tree: 110 places in 16 repositories, the survey's count. `teeth-*.txt` are full teeth runs on forge (stack-up 338 cases, scopyx 55). `new-cases/` holds the gate's own cases run alone on forge, through a copy of each harness that skips the others; agent-passport, engram and verdryx say there that their Python package is not installed, and their cases ran in CI.

Agent-passport, architecture, engram, mockryx, taipan and terraform-provider-taipan each had one place, the teeth harness reading a gate's output, so no gate of theirs carried it and none was looped. verdryx's `readme-numbers.sh` needs its test suite and catalog's `templates-load.sh` needs sibling checkouts, so CI ran those.
