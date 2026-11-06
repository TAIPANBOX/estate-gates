#!/usr/bin/env bash
# scopyx: every gate with the construct, and the same fault planted before and after
W=$HOME/pipe-readers-2026-11-06
export PATH=$PATH:/usr/local/go/bin:$HOME/go/bin
tree=$1; tag=$2
while pgrep -f 'gate-loop.sh .*green-stack-up' >/dev/null; do sleep 3; done
bash $W/gate-loop.sh $tree $W/out/$tag-scopyx 100 6 ./scripts/no-warm-context.sh ./scripts/no-delegated-decisions.sh ./scripts/meta-key-stops-at-the-door.sh ./scripts/one-way-out.sh ./scripts/no-compliance-claims.sh
rm -rf $tree-fault; cp -a $tree $tree-fault
cd $tree-fault || exit 1
python3 - <<'PY'
p='internal/backend/chromium.go'
s=open(p).read()
i=s.index('\n',s.index('package '))+1
open(p,'w').write(s[:i]+'\nvar _ = "cookiejar"\n'+s[i:])
PY
bash $W/gate-loop.sh $tree-fault $W/out/$tag-fault-scopyx 100 6 ./scripts/no-warm-context.sh
