"""Record exact staged build inputs, source refs and dirty diff digests without secrets.

Run after build.sh; this proves inputs, not an image import or a deployment.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import sys


def digest(data):
    return hashlib.sha256(data).hexdigest()


def git(path, *args):
    return subprocess.check_output(["git", "-C", str(path), *args])


def manifest(root):
    trigger = root / "be-validator-agent/trigger"
    paths = list((trigger / "build/pkg").rglob("*")) + list((trigger / "build/light").rglob("*"))
    paths += list((root / "be-document-processing/src").rglob("*"))
    paths += list((root / "be-intake/app").glob("*.py"))
    paths += [root / p for p in (
        "be-intake/app/Dockerfile", "be-intake/app/requirements.txt",
        "be-document-processing/pyproject.toml", "be-document-processing/requirements.txt",
        "be-validator-agent/trigger/build.sh", "be-validator-agent/trigger/Dockerfile",
        "be-validator-agent/trigger/requirements-worker.txt")]
    inputs = {str(p.relative_to(root)): digest(p.read_bytes()) for p in sorted(set(paths))
              if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"}
    owners = [root, root / "be-validator-agent", root / "be-intake", root / "be-document-processing"]
    refs = {str(p.relative_to(root)) or ".": {
        "git_root": git(p, "rev-parse", "--show-toplevel").decode().strip(),
        "head": git(p, "rev-parse", "HEAD").decode().strip(),
        "dirty_diff_sha256": digest(git(p, "diff", "--binary")),
        "status_sha256": digest(git(p, "status", "--porcelain=v1")),
    } for p in owners}
    return {"schema_version": 1, "inputs": inputs, "source_refs": refs,
            "inputs_sha256": digest(json.dumps(inputs, sort_keys=True).encode()),
            "scope": "staged inputs only; image resolved dependencies/import/deployment need separate proof"}


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[3]
    data = manifest(root)
    if len(sys.argv) == 2:
        destination = Path(sys.argv[1]).resolve()
        destination.relative_to(root)
        destination.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"inputs_sha256": data["inputs_sha256"], "file_count": len(data["inputs"])}))
