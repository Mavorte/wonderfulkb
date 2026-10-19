"""Spustí kontraktový test nad fixturami jako podproces (je to skript, ne sada pytest testů)."""
import os
import subprocess
import sys


def test_contract_over_fixtures():
    here = os.path.dirname(os.path.abspath(__file__))
    r = subprocess.run([sys.executable, "contract_test.py"], cwd=here, capture_output=True, text=True,
                       env={**os.environ, "FIXTURES": "1", "API_KEY": "fake-test-key"})
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-2000:]
    assert "FAIL" not in r.stdout
