from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

CaseId = Annotated[str, Field(pattern=r"^[A-Za-z0-9._-]{1,128}$")]
DocumentType = Literal[
    "loan_agreement", "invoice", "order", "handover", "repayment_schedule",
    "security_transfer", "guarantee", "insurance", "payment_confirmation",
    "terms", "technical_specification", "other", "unknown",
]
Role = Literal["provider", "borrower", "buyer", "supplier", "guarantor", "insurer", "unknown"]
FieldKey = Literal[
    "entity.name", "entity.ico", "entity.dic", "entity.address",
    "contract.number", "invoice.number", "order.number", "asset.name",
    "asset.serial", "asset.year", "asset.condition", "purchase.net",
    "purchase.vat", "purchase.gross", "loan.principal", "loan.annual_rate",
    "loan.term_months", "loan.own_funds", "loan.total", "payment.amount",
    "payment.account", "payment.frequency", "installment.amount",
    "installment.count", "date.issued", "date.signed", "date.due", "date.handover",
]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class UploadRequest(Contract):
    filename: str = Field(min_length=1, max_length=255)
    content_type: Literal["application/pdf", "image/png", "image/jpeg"]
    size_bytes: int = Field(gt=0, le=25 * 1024 * 1024)
    mode: Literal["visual", "auto"] = "auto"

    @field_validator("filename")
    @classmethod
    def filename_only(cls, value):
        if any(c in value for c in ["/", "\\", "\x00", "\r", "\n"]):
            raise ValueError("filename must not contain a path or control characters")
        return value


class BBox(Contract):
    coordinates: list[float] = Field(min_length=4, max_length=4)

    @field_validator("coordinates")
    @classmethod
    def check_box(cls, v):
        if not (0 <= v[0] <= v[2] <= 1 and 0 <= v[1] <= v[3] <= 1):
            raise ValueError("invalid normalized bounding box")
        return v


class Evidence(Contract):
    page_number: int = Field(ge=1)
    block_id: str
    quote: str = Field(min_length=1)
    bbox: list[float] | None = None


class Block(Contract):
    block_id: str
    type: str = "paragraph"
    text: str
    bbox: list[float] | None
    confidence: float | None = Field(default=None, ge=0, le=1)

    @field_validator("bbox")
    @classmethod
    def check_box(cls, value):
        if value is not None:
            BBox(coordinates=value)
        return value


class Cell(Contract):
    row: int = Field(ge=0)
    column: int = Field(ge=0)
    row_span: int = Field(default=1, ge=1)
    column_span: int = Field(default=1, ge=1)
    text: str


class Table(Contract):
    table_id: str
    block_id: str | None = None
    html: str | None = None
    cells: list[Cell] = Field(default_factory=list)


class Page(Contract):
    page_number: int = Field(ge=1)
    status: Literal["completed", "failed"]
    method: Literal["vision", "native"]
    width: float
    height: float
    text: str
    markdown: str | None = None
    blocks: list[Block] = Field(default_factory=list)
    tables: list[Table] = Field(default_factory=list)
    visual_marks: list[dict] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    error: str | None = None
    model: str | None = None


class DraftField(Contract):
    key: FieldKey
    role: Role | None
    raw_value: str | None
    status: Literal["extracted", "not_found", "unreadable", "ambiguous"]
    evidence: list[Evidence]

    @model_validator(mode="after")
    def require_evidence(self):
        if self.status == "extracted" and (not self.raw_value or not self.evidence):
            raise ValueError("extracted fields require a raw value and source evidence")
        return self


class ExtractionDraft(Contract):
    document_type: DocumentType
    fields: list[DraftField]
    warnings: list[str]


class Correction(Contract):
    run_id: str
    field_id: str
    normalized_value: str | None
    reason: str = Field(min_length=3, max_length=1000)
    # A correction is an assertion by the reviewer, never an OCR observation.


class CreateCaseRequest(Contract):
    case_id: CaseId
    client_id: str
    metadata: dict | None = None


ProcessingStatus = Literal["awaiting_upload", "queued", "processing", "completed", "partial", "failed"]


class DocumentRecord(Contract):
    schema_version: Literal["1.0"]
    case_id: CaseId
    client_id: str
    document_id: str
    filename: str
    content_type: str
    size_bytes: int
    mode: Literal["visual", "auto"]
    processing_status: ProcessingStatus
    source_sha256: str | None
    created_at: str
    updated_at: str
    job_id: str | None
    run_id: str | None
    page_count: int | None = None
    document_type: DocumentType | None = None
    errors: list[dict] = Field(default_factory=list)
    error: str | None = None


class UploadResponse(Contract):
    document: DocumentRecord
    upload: dict


class DocumentList(Contract):
    documents: list[DocumentRecord]


class AcceptedJob(Contract):
    job_id: str
    document_id: str
    processing_status: ProcessingStatus


class ExtractedField(Contract):
    field_id: str
    key: FieldKey
    role: Role | None
    raw_value: str | None
    normalized_value: str | None
    currency: str | None = None
    status: Literal["extracted", "not_found", "unreadable", "ambiguous", "human_corrected"]
    evidence: list[Evidence]
    original_normalized_value: str | None = None
    correction_id: str | None = None


class ExtractionResult(Contract):
    schema_version: Literal["1.0"]
    document_type: DocumentType
    fields: list[ExtractedField]
    warnings: list[str]
    model: str | None
    prompt_version: str | None = None


class OcrResult(Contract):
    pages: list[Page]


class DocumentResult(Contract):
    schema_version: Literal["1.0"]
    case_id: CaseId
    client_id: str
    document_id: str
    run_id: str
    source_sha256: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    page_count: int = Field(ge=1)
    processing_status: Literal["completed", "partial", "failed"]
    ocr: OcrResult
    extraction: ExtractionResult
    errors: list[dict]
    processing: dict
    corrections: list[dict] = Field(default_factory=list)

    @model_validator(mode="after")
    def all_pages_present(self):
        if [p.page_number for p in self.ocr.pages] != list(range(1, self.page_count + 1)):
            raise ValueError("all pages must be present once, in source order")
        return self
