import sys
from pathlib import Path

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[2]))  # infra/validator-agent: balíček `classify`
sys.path.insert(0, str(HERE.parents[1]))  # infra/validator-agent/classify: skript `evaluate`
