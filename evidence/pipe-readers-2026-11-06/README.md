# Pipes into a grep that leaves early, 2026-11-06

`gate-loop.sh TREE OUT N LOADERS gate...` runs each gate N times beside LOADERS busy loops and writes one line per gate to `OUT/result.tsv`: gate, failures, runs, seconds, the first failing line. Forge, 4 cores, bash 5.2.37, GNU grep 3.11.

| Directory | Tree | N | Busy loops |
|---|---|---|---|
| `idle-*` | before, every gate of the callers | 1 | 0 |
| `red-*` | before: stack-k8s `f3eb0fd`, stack-single `6ee1655`, the gates with the construct | 30 | 6 |
| `green-*` | after, the same gates | 30 | 6 |
| `cost-base`, `cost-fixed` | `costcrew-ceiling-is-set.sh`, before and after | 300 | 6 |
| `final-*` | the merged tree, every gate of the callers | 1 | 0 |

`gate-red-*.txt` is `scripts/no-reader-leaves-a-pipe-early.sh` run over the old trees. In `idle-stack-k8s` four gates are red for want of `kubeconform`, `kubectl` and `go` on PATH, which the later runs had; no other line there is red.
