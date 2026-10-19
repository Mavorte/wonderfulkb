#!/usr/bin/env bash
# Vytvoří .venv se závislostmi testů (moto, pipeline, API, ingest). Do AWS nesahá.
set -euo pipefail
cd "$(dirname "$0")"
python3 -m venv .venv
.venv/bin/pip install -q -r requirements-dev.txt
echo "ready: .venv/bin/python -m pytest -q"
