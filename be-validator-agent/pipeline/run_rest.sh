#!/usr/bin/env bash
# Finishes the dataset after the pilot (SYN-A01, SYN-B01, SYN-C01). Idempotent: documents already `completed`
# by this pipeline version are skipped (--resume), so it can be started again after any interruption.
#   ./run_rest.sh                # foreground; or: nohup ./run_rest.sh >/dev/null 2>&1 &
# Order: remaining SYN-* cases (mapping.json), unhappy_scenario, solom-rec, stavby-fiser.
# The last three run with --skip signatures: the signatures.json written by the signature session stays as it is.
# Rate: vision 20 requests/min, embed 25/min (both overridable through the same variables). Stops after
# MAX_BAD documents that did not end completed (systematic error). Log and per-case reports go to runs/.
set -u
cd "$(dirname "$0")"
export AWS_PROFILE="${AWS_PROFILE:-hackathon}" AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-eu-central-1}"
export PIPELINE_BEDROCK_RPM="${PIPELINE_BEDROCK_RPM:-20}" WONDERFULKB_BEDROCK_RPM="${WONDERFULKB_BEDROCK_RPM:-25}"
MAX_BAD="${MAX_BAD:-6}"
PY=.venv/bin/python
mkdir -p runs
LOG="runs/run_rest-$(date +%Y%m%d-%H%M%S).log"
exec > >(tee -a "$LOG") 2>&1
echo "start $(date +%T) log=$LOG"

SYN=$($PY -I -c "
import json
m = json.load(open('../dataset/mapping.json'))
print(' '.join(c['case_id'] for c in m['cases'] if c['case_id'] not in ('SYN-A01', 'SYN-B01', 'SYN-C01')))")

bad=0
check() {  # count documents of one report that are not completed
  n=$($PY -I -c "
import json, sys
try:
    docs = json.load(open('runs/$1.json'))['documents']
except FileNotFoundError:
    docs = []
print(sum(d['status'] != 'completed' for d in docs))")
  bad=$((bad + n))
  if [ "$bad" -ge "$MAX_BAD" ]; then
    echo "STOP: $bad documents did not end completed (limit $MAX_BAD), last case $1. Fix the cause, then run again."
    exit 2
  fi
}

for c in $SYN; do
  echo "=== $c $(date +%T)"
  $PY -I -m pipeline run_case "$c" --resume --report "runs/$c.json"
  check "$c"
done
for pair in "unhappy_scenario cases/unhappy_scenario/" "solom-rec cases/solom-rec/original/" "stavby-fiser cases/stavby-fiser/original/"; do
  set -- $pair
  echo "=== $1 $(date +%T)"
  $PY -I -m pipeline run_prefix "$1" "$2" --skip signatures --resume --report "runs/$1.json"
  check "$1"
done

echo "=== summary $(date +%T)"
$PY -I -c "
import glob, json
print(f\"{'případ':<20}{'dokumentů':>10}{'completed':>10}{'partial':>8}{'failed':>7}{'s':>7}\")
for path in sorted(glob.glob('runs/*.json')):
    docs = json.load(open(path))['documents']
    count = lambda s: sum(d['status'] == s for d in docs)
    print(f\"{path[5:-5]:<20}{len(docs):>10}{count('completed'):>10}{count('partial'):>8}{count('failed'):>7}{sum(d['seconds'] for d in docs):>7.0f}\")
"
echo "done $(date +%T)"
