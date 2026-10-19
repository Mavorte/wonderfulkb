import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    backend: str = "local"
    provider: str = "local"
    data_dir: Path = Path(".local-data")
    public_url: str = "http://127.0.0.1:8010"
    api_key: str = field(default="", repr=False)
    ocr_model: str = "qwen.qwen3-vl-235b-a22b-instruct"
    extraction_model: str = "qwen.qwen3-vl-235b-a22b-instruct"
    bedrock_region: str = "eu-central-1"
    bedrock_api: str = "mantle"
    max_bytes: int = 25 * 1024 * 1024
    max_pages: int = 50
    max_attempts: int = 3
    lease_seconds: int = 600
    worker_enabled: bool = True
    documents_table: str = ""
    cases_table: str = ""
    clients_table: str = ""
    bucket: str = ""
    queue_url: str = ""
    allowed_origin: str = "http://localhost:3200"
    signatures_enabled: bool = False

    def __post_init__(self):
        if self.bedrock_region != "eu-central-1":
            raise ValueError("Document processing is restricted to eu-central-1 (Frankfurt)")
        if self.backend == "aws" and os.getenv("AWS_REGION", "eu-central-1") != "eu-central-1":
            raise ValueError("Deploy document processing in eu-central-1 (Frankfurt)")

    @classmethod
    def from_env(cls):
        return cls(
            backend=os.getenv("STORAGE_BACKEND", "local"),
            provider=os.getenv("OCR_PROVIDER", "local"),
            data_dir=Path(os.getenv("DATA_DIR", ".local-data")),
            public_url=os.getenv("PUBLIC_URL", "http://127.0.0.1:8010").rstrip("/"),
            api_key=os.getenv("DOCUMENT_API_KEY", ""),
            ocr_model=os.getenv("BEDROCK_OCR_MODEL", "qwen.qwen3-vl-235b-a22b-instruct"),
            extraction_model=os.getenv("BEDROCK_EXTRACTION_MODEL", "qwen.qwen3-vl-235b-a22b-instruct"),
            bedrock_region=os.getenv("BEDROCK_REGION", "eu-central-1"),
            bedrock_api=os.getenv("BEDROCK_API", "mantle"),
            worker_enabled=os.getenv("WORKER_ENABLED", "true").lower() == "true",
            documents_table=os.getenv("DOCUMENTS_TABLE_NAME", ""),
            cases_table=os.getenv("CASES_TABLE_NAME", ""),
            clients_table=os.getenv("CLIENTS_TABLE_NAME", ""),
            bucket=os.getenv("DOCUMENTS_BUCKET", ""),
            queue_url=os.getenv("QUEUE_URL", ""),
            allowed_origin=os.getenv("ALLOWED_ORIGIN", "http://localhost:3200"),
            signatures_enabled=os.getenv("SIGNATURES_ENABLED", "false").lower() == "true",
        )
