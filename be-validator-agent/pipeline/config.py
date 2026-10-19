"""Settings of the document pipeline, all overridable through environment variables."""
import os
from dataclasses import dataclass, field

PIPELINE_VERSION = "1.0.0"
STEPS = ("classify", "embed", "signatures", "copy")


def _skip_from_env():
    return frozenset(s.strip() for s in os.environ.get("PIPELINE_SKIP", "").split(",") if s.strip())


@dataclass(frozen=True)
class Settings:
    region: str = field(default_factory=lambda: os.environ.get("AWS_DEFAULT_REGION") or "eu-central-1")
    bucket: str = field(default_factory=lambda: os.environ.get("PIPELINE_BUCKET", "wonderfulkb-raw-document-storage"))
    documents_table: str = field(default_factory=lambda: os.environ.get("PIPELINE_DOCUMENTS_TABLE", "wonderfulkb-uw-documents"))
    analysis_table: str = field(default_factory=lambda: os.environ.get("PIPELINE_ANALYSIS_TABLE", "wonderfulkb-uw-document-analysis"))
    vision_model: str = field(default_factory=lambda: os.environ.get("PIPELINE_VISION_MODEL", "qwen.qwen3-vl-235b-a22b-instruct"))
    # The whole team shares 50 Bedrock requests per minute; stay well below by default.
    bedrock_rpm: float = field(default_factory=lambda: float(os.environ.get("PIPELINE_BEDROCK_RPM", "20")))
    page_dpi: float = 110          # stored pages/<n>.png (embeddings, human review)
    vision_dpi: float = 150        # render sent to the vision model
    max_pixels: int = 2400         # longest side of any render
    max_vision_pages: int = field(default_factory=lambda: int(os.environ.get("PIPELINE_MAX_VISION_PAGES", "30")))
    max_pdf_bytes: int = 50 * 1024 * 1024
    skip: frozenset = field(default_factory=_skip_from_env)  # subset of STEPS
