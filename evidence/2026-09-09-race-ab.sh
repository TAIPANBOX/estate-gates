#!/usr/bin/env bash
# Does the sensor report the destination the kernel used, or one a second thread
# left in the buffer for it? Ground truth is connect()'s own return value.
set -uo pipefail

apt-get update -qq >/dev/null 2>&1
apt-get install -y -qq gcc python3 >/dev/null 2>&1
gcc -O2 -pthread -o /tmp/toctou_race /live/toctou_race.c || exit 1
echo "race probe built; $(nproc) CPUs"
echo

N="${1:-20000}"

for v in old new; do
	echo "=========================================================="
	echo "=== sensor: $v"
	echo "=========================================================="
	( sleep 2; /tmp/toctou_race "$N" ) &
	wpid=$!
	"/live/idryx-$v" ebpf-capture -duration 12s -out "/live/race-$v.json" 2>&1 | grep -E 'captured|not reported|WARNING'
	wait $wpid
	python3 - "$v" <<'PY'
import json, sys
v = sys.argv[1]
d = json.load(open(f"/live/race-{v}.json"))
flows = d.get("flows", [])
mine = [f for f in flows if f["identity"].startswith("proc:toctou_race")]
p11434 = sum(1 for f in mine if f["destination"].endswith(":11434"))
p8000 = sum(1 for f in mine if f["destination"].endswith(":8000"))
print(f"SENSOR SAID:                        {p11434} to :11434, {p8000} to :8000  ({len(mine)} attributed flows)")
PY
	echo
done
