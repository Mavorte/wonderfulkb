from dataclasses import dataclass, field


@dataclass
class Detection:
    """A candidate signature on one page. `bbox` is [x0, y0, x1, y1], relative to the page (0..1)."""
    page: int
    bbox: list[float]
    detector: str  # textract | vision_llm
    score: float | None
    # Role found upstream (e.g. from Textract LINE blocks), used only when the PDF text gives none.
    hint: dict | None = None


@dataclass
class TextLine:
    """A line of text on a page, in page points (origin top-left)."""
    text: str
    x0: float
    y0: float
    x1: float
    y1: float


@dataclass
class Signature:
    signature_id: str
    page: int
    bbox: list[float]
    detector: str
    detection_score: float | None
    role: str | None = None
    role_source: str | None = None
    role_evidence: str | None = None
    crop_url: str | None = None
    crop_path: str | None = None
    crop_s3_key: str | None = None      # set when the crop store is S3
    crop_encrypted: bool | None = None
    phash: str | None = None
    copy_suspicion: dict = field(default_factory=lambda: {"level": "none", "matches": []})
    # Internal, not serialised: ink mask for the pixel check.
    mask: object = field(default=None, repr=False, compare=False)
    aspect: float | None = field(default=None, repr=False, compare=False)

    def to_api(self, with_crop_url=True) -> dict:
        out = {
            "signature_id": self.signature_id, "page": self.page,
            "bbox": [round(v, 4) for v in self.bbox],
            "detector": self.detector,
            "detection_score": None if self.detection_score is None else round(self.detection_score, 1),
            "role": self.role, "role_source": self.role_source, "role_evidence": self.role_evidence,
            "crop_url": self.crop_url, "phash": self.phash,
            "copy_suspicion": self.copy_suspicion,
        }
        if self.crop_s3_key:
            out["crop_s3_key"] = self.crop_s3_key
            out["crop_encrypted"] = bool(self.crop_encrypted)
        if not with_crop_url:
            del out["crop_url"]   # the API adds a presigned URL itself
        return out
