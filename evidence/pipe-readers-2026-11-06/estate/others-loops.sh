#!/usr/bin/env bash
# the other repositories: gates with the construct, before and after, one repository at a time
W=$HOME/pipe-readers-2026-11-06
export PATH=$PATH:/usr/local/go/bin:$HOME/go/bin
run() { # repo n gate...
  r=$1; n=$2; shift 2
  bash $W/gate-loop.sh $W/base/$r $W/out/red-$r $n 6 "$@"
  bash $W/gate-loop.sh $W/fixed/$r $W/out/green-$r $n 6 "$@"
}
run trailryx 20 ./scripts/gate-count.sh
run catalog 100 ./scripts/no-executables.sh
run idryx 20 ./scripts/ebpf-optional.sh
echo finished >$W/out/others-done
