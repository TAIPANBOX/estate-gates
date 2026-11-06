#!/usr/bin/env bash
# usage: gate-loop.sh TREE OUT N LOADERS gate...
# Runs each gate N times beside LOADERS busy loops, one line per gate in OUT/result.tsv.
tree=$1; out=$2; n=$3; load=$4; shift 4
mkdir -p "$out"; cd "$tree" || exit 1
pids=()
for i in $(seq 1 "$load"); do ( while :; do :; done ) & pids+=($!); done
trap '[ ${#pids[@]} -eq 0 ] || kill "${pids[@]}" 2>/dev/null' EXIT
: >"$out/result.tsv"
for g in "$@"; do
  bad=0; sample=""; s=$(date +%s)
  for i in $(seq 1 "$n"); do
    o=$(timeout 600 "$g" 2>&1); rc=$?
    if [ "$rc" -ne 0 ]; then
      bad=$((bad+1))
      if [ -z "$sample" ]; then sample="rc=$rc $(grep -E -m1 'FAIL|fail|error' <<<"$o" | cut -c1-180)"; fi
    fi
  done
  printf '%s\t%d\t%d\t%ds\t%s\n' "$g" "$bad" "$n" "$(( $(date +%s)-s ))" "$sample" >>"$out/result.tsv"
done
echo finished >"$out/done"
