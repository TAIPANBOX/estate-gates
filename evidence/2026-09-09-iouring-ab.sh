#!/usr/bin/env bash
# The A/B the change exists for: one io_uring connection and one ordinary
# connection, under the sensor as it is on main and under the sensor as this
# branch makes it.
set -uo pipefail

echo "=== kernel ==="
uname -r
echo

apt-get update -qq >/dev/null 2>&1
apt-get install -y -qq gcc liburing-dev python3 netcat-openbsd >/dev/null 2>&1
gcc -O2 -o /tmp/iouring_connect /live/iouring_connect.c -luring || {
	echo "could not build the io_uring probe"
	exit 1
}
echo "io_uring probe built"
echo

# The same workload under each sensor: one io_uring connect, one ordinary
# connect, both to 127.0.0.1:11434 so nothing leaves the machine and both
# survive idryx's loopback filter.
workload() {
	sleep 2
	/tmp/iouring_connect
	nc -w 1 127.0.0.1 11434 </dev/null >/dev/null 2>&1
	echo "ordinary connect() to 127.0.0.1:11434 done"
}

for v in old new; do
	echo "=========================================================="
	echo "=== sensor: $v"
	echo "=========================================================="
	workload &
	wpid=$!
	"/live/idryx-$v" ebpf-capture -duration 6s -out "/live/out-$v.json" 2>&1 | tail -5
	wait $wpid
	echo "--- flows captured by $v ---"
	python3 - "$v" <<'PY'
import json, sys
v = sys.argv[1]
try:
    d = json.load(open(f"/live/out-{v}.json"))
except Exception as e:
    print("could not read the capture:", e)
    raise SystemExit
flows = d.get("flows", [])
print(f"{len(flows)} flow(s)")
for f in flows:
    print(f"  {f['identity']:28} -> {f['destination']}")
hit = [f for f in flows if f["destination"].endswith(":11434")]
print(f"  connections to 127.0.0.1:11434 seen: {len(hit)}")
PY
	echo
done
