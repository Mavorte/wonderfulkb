#!/usr/bin/env bash
# Stages the Lambda packages in build/ from the sibling modules (read only, nothing is written outside trigger/):
#   build/light/  zip package of the enqueue and DLQ functions (trigger/ only, boto3 comes with the runtime)
#   build/pkg/    Docker context of the worker image: trigger/, pipeline/, classify/, embed/, dedup/,
#                 signatures/signature_pipeline, privacy/signature_privacy, regions/region_pipeline (with labels.yaml)
#                 and requirements.txt
# The sibling modules are copied as they are on disk at this moment, so build right before deploying.
set -euo pipefail
cd "$(dirname "$0")"
SRC=..
rm -rf build
mkdir -p build/light/trigger build/pkg/trigger build/pkg/signatures build/pkg/privacy build/pkg/regions
COMMON=(--exclude __pycache__ --exclude '*.pyc' --exclude tests --exclude .venv --exclude '.pytest_cache')
for f in __init__ common enqueue_handler dlq_handler; do cp "$f.py" build/light/trigger/; done
for f in __init__ common enqueue_handler dlq_handler worker_handler case_step wonderful_webhook; do cp "$f.py" build/pkg/trigger/; done
rsync -a "${COMMON[@]}" --exclude runs --exclude '*.sh' --exclude '*.yaml' --exclude '*.md' --exclude 'requirements*.txt' \
  --exclude pytest.ini --exclude measure.py "$SRC/pipeline/" build/pkg/pipeline/
rsync -a "${COMMON[@]}" --exclude evaluate.py "$SRC/classify/" build/pkg/classify/
rsync -a "${COMMON[@]}" --exclude benchmark.py --exclude live_check.py "$SRC/embed/" build/pkg/embed/
rsync -a "${COMMON[@]}" --exclude backfill.py --exclude '*.sh' --exclude '*.yaml' --exclude '*.md' --exclude 'requirements*.txt' \
  --exclude pytest.ini "$SRC/dedup/" build/pkg/dedup/
rsync -a "${COMMON[@]}" "$SRC/signatures/signature_pipeline/" build/pkg/signatures/signature_pipeline/
rsync -a "${COMMON[@]}" "$SRC/privacy/signature_privacy/" build/pkg/privacy/signature_privacy/
rsync -a "${COMMON[@]}" "$SRC/regions/region_pipeline/" build/pkg/regions/region_pipeline/
cp requirements-worker.txt build/pkg/requirements.txt
cp Dockerfile build/pkg/Dockerfile
echo "staged: build/light ($(du -sk build/light | cut -f1) kB), build/pkg ($(du -sk build/pkg | cut -f1) kB, without dependencies)"
