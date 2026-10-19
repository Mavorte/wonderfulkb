"""Regenerate the checked-in API and result schemas without creating data files."""
import json
import tempfile
from pathlib import Path

from document_processing.api import create_app
from document_processing.config import Settings
from document_processing.models import DocumentResult

root = Path(__file__).resolve().parents[1]
destination = root / "contracts"
destination.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory() as directory:
    app = create_app(Settings(data_dir=Path(directory), worker_enabled=False))
    specification = app.openapi()
    # The cloud contract excludes local-only client/case emulation and raw PUT.
    specification["paths"] = {p: v for p, v in specification["paths"].items() if "/documents" in p or p.endswith("/validation")}
    specification["components"].setdefault("securitySchemes", {})["ApiKeyAuth"] = {
        "type": "apiKey", "in": "header", "name": "x-api-key"}
    specification["security"] = [{"ApiKeyAuth": []}]
    specification["servers"] = [{"url": "http://127.0.0.1:8010"}]
    (destination / "openapi-ingest.json").write_text(json.dumps(specification, ensure_ascii=False, indent=2) + "\n")
(destination / "document-result.schema.json").write_text(json.dumps(DocumentResult.model_json_schema(), ensure_ascii=False, indent=2) + "\n")
