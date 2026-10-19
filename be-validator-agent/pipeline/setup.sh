#!/usr/bin/env bash
# Creates .venv, installs dependencies and makes infra/validator-agent importable, so that
#   .venv/bin/python -I -m pipeline run_case <case_id>
# works from any directory (-I ignores PYTHONPATH and the current directory) and classify/, embed/ resolve.
set -euo pipefail
cd "$(dirname "$0")"
python3 -m venv .venv
.venv/bin/pip install -q -r requirements-dev.txt
site=$(.venv/bin/python -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')
dirname "$PWD" > "$site/wonderfulkb_validator_agent.pth"
echo "ready: .venv/bin/python -I -m pipeline --help"
