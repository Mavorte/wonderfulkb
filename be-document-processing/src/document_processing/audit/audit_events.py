"""The content-free FileReceived envelope."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
import math
import re
from typing import Mapping


EVENT_FIELDS = (
    "schema_version", "event_id", "case_id", "document_id", "sequence", "type", "occurred_at",
)
RUN_CONTEXT_FIELDS = ("source",)


def _integer(value):
    if isinstance(value, Decimal) and value.is_finite() and value == value.to_integral_value():
        return int(value)
    return value


def _envelope(item):
    values = {name: item[name] for name in EVENT_FIELDS}
    for name in ("schema_version", "sequence"):
        values[name] = _integer(values[name])
    return values


def _attempt_values(item):
    return {**_envelope(item), "run_id": item["run_id"],
            "attempt_no": _integer(item["attempt_no"])}


def _duration(value):
    if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float, Decimal))
                              or not math.isfinite(value) or value < 0):
        raise ValueError("duration_ms must be finite and nonnegative")


def _stored_duration(item):
    value = item.get("duration_ms")
    return float(value) if value is not None else None


@dataclass(frozen=True)
class FileReceived:
    schema_version: int
    event_id: str
    case_id: str
    document_id: str
    sequence: int
    type: str
    occurred_at: str

    def __post_init__(self):
        if type(self.schema_version) is not int or self.schema_version != 1:
            raise ValueError("Unsupported audit schema version")
        if self.type != type(self).__name__:
            raise ValueError("Unsupported audit event type")
        for name in ("event_id", "case_id", "document_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a nonempty string")
        if type(self.sequence) is not int or self.sequence < 0:
            raise ValueError("sequence must be a nonnegative integer")
        if not isinstance(self.occurred_at, str) or "T" not in self.occurred_at:
            raise ValueError("occurred_at must be a UTC ISO timestamp")
        try:
            timestamp = datetime.fromisoformat(self.occurred_at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("occurred_at must be a UTC ISO timestamp") from exc
        if timestamp.utcoffset() != timedelta(0):
            raise ValueError("occurred_at must be a UTC ISO timestamp")

    def to_item(self) -> dict:
        """Explicit allowlist: never serialize arbitrary instance attributes."""
        return {name: getattr(self, name) for name in EVENT_FIELDS}

    @classmethod
    def from_item(cls, item: Mapping) -> "FileReceived":
        return cls(**_envelope(item))


@dataclass(frozen=True)
class RunQueued(FileReceived):
    run_id: str
    run_context: Mapping[str, str] | None = None

    def __post_init__(self):
        # Reuse all common envelope checks without accepting FileReceived here.
        super(RunQueued, self).__post_init__()
        if not isinstance(self.run_id, str) or not self.run_id.strip():
            raise ValueError("run_id must be a nonempty string")
        context = self.run_context
        if context is not None and not isinstance(context, Mapping):
            raise ValueError("run_context must be a mapping")

    def to_item(self) -> dict:
        item = super().to_item()
        item["run_id"] = self.run_id
        context = self.run_context or {}
        approved = {key: value for key, value in context.items()
                    if key in RUN_CONTEXT_FIELDS and isinstance(value, str) and value.strip()}
        if approved:
            item["run_context"] = approved
        return item

    @classmethod
    def from_item(cls, item: Mapping) -> "RunQueued":
        values = _envelope(item)
        context = item.get("run_context")
        if isinstance(context, Mapping):
            context = {key: value for key, value in context.items()
                       if key in RUN_CONTEXT_FIELDS and isinstance(value, str) and value.strip()}
        return cls(**values, run_id=item["run_id"], run_context=context)


STEP_ERROR_CODES = frozenset({"PIPELINE_CONFIG_CHANGED", "SOURCE_HASH_MISMATCH", "SOURCE_VALIDATION_FAILED", "EXTRACTION_FAILED", "PAGE_TRANSCRIPTION_FAILED", "RESULT_PUBLISHING_FAILED", "SIGNATURE_DETECTION_FAILED"})
STEP_STAGES = frozenset({"source_validation", "extraction", "result_publishing", "signature_detection"})


@dataclass(frozen=True)
class ResultPublished(FileReceived):
    """Explicit producer observation after the complete owned publish boundary.

    event_id is also the stable publication identity; no run terminal is implied.
    """
    run_id: str
    attempt_no: int
    result_status: str
    artifact_ids: tuple[str, ...] | None = None

    def __post_init__(self):
        FileReceived.__post_init__(self)
        if not isinstance(self.run_id, str) or not self.run_id.strip():
            raise ValueError("run_id must be a nonempty string")
        if type(self.attempt_no) is not int or self.attempt_no <= 0:
            raise ValueError("attempt_no must be positive")
        if self.result_status not in {"completed", "partial", "failed"}:
            raise ValueError("unsupported publication status")
        if self.artifact_ids is not None:
            if (not isinstance(self.artifact_ids, (list, tuple)) or any(
                    not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9._-]{1,256}", value)
                    for value in self.artifact_ids)):
                raise ValueError("artifact_ids must be opaque references")
            object.__setattr__(self, "artifact_ids", tuple(self.artifact_ids))

    def to_item(self):
        item = super().to_item()
        item.update(run_id=self.run_id, attempt_no=self.attempt_no, result_status=self.result_status)
        if self.artifact_ids is not None:
            item["artifact_ids"] = list(self.artifact_ids)
        return item

    @classmethod
    def from_item(cls, item):
        allowed = set(EVENT_FIELDS) | {"run_id", "attempt_no", "result_status", "artifact_ids", "pk", "sk"}
        if set(item) - allowed:
            raise ValueError("unsupported publication fields")
        return cls(**_attempt_values(item), result_status=item["result_status"], artifact_ids=item.get("artifact_ids"))


@dataclass(frozen=True)
class StepStarted(FileReceived):
    run_id: str
    attempt_no: int
    stage: str
    page_number: int | None = None

    def __post_init__(self):
        FileReceived.__post_init__(self)
        if not isinstance(self.run_id, str) or not self.run_id.strip():
            raise ValueError("run_id must be a nonempty string")
        if type(self.attempt_no) is not int or self.attempt_no <= 0:
            raise ValueError("attempt_no must be a positive integer")
        if self.stage == "page_transcription":
            if self.type not in {"StepStarted", "PageCompleted", "PageFailed"} or type(self.page_number) is not int or self.page_number < 1:
                raise ValueError("Invalid page transcription scope")
        elif self.stage not in STEP_STAGES or self.page_number is not None or self.type not in {"StepStarted", "StepFinished", "StepFailed"}:
            raise ValueError("Unsupported audit step")

    def to_item(self):
        item = super().to_item()
        item.update(run_id=self.run_id, attempt_no=self.attempt_no, stage=self.stage)
        if self.page_number is not None: item["page_number"] = self.page_number
        return item

    @classmethod
    def from_item(cls, item):
        return cls(**_step_values(item))


@dataclass(frozen=True)
class StepFinished(StepStarted):
    duration_ms: float | None = None

    def __post_init__(self):
        StepStarted.__post_init__(self)
        if self.type not in {"StepFinished", "StepFailed"}: raise ValueError("Unsupported audit event type")
        _duration(self.duration_ms)

    def to_item(self):
        item = super().to_item()
        if self.duration_ms is not None: item["duration_ms"] = Decimal(str(self.duration_ms))
        return item

    @classmethod
    def from_item(cls, item):
        return cls(**_step_values(item), duration_ms=_stored_duration(item))


@dataclass(frozen=True)
class StepFailed(StepFinished):
    error_code: str = "SOURCE_VALIDATION_FAILED"

    def __post_init__(self):
        StepFinished.__post_init__(self)
        if self.type != "StepFailed" or self.error_code not in STEP_ERROR_CODES: raise ValueError("Unsupported audit error code")

    def to_item(self):
        item = super().to_item(); item["error_code"] = self.error_code; return item

    @classmethod
    def from_item(cls, item):
        return cls(**_step_values(item), duration_ms=_stored_duration(item), error_code=item["error_code"])


def _step_values(item):
    return {**_attempt_values(item), "stage": item["stage"],
            "page_number": _integer(item["page_number"]) if "page_number" in item else None}


@dataclass(frozen=True)
class PageCacheReused(FileReceived):
    """A validated, previously stored page result reused by this attempt."""
    run_id: str
    attempt_no: int
    stage: str
    page_number: int
    cached_status: str
    cached_method: str | None = None
    cached_model: str | None = None
    artifact_ids: tuple[str, ...] | None = None

    def __post_init__(self):
        FileReceived.__post_init__(self)
        if not isinstance(self.run_id, str) or not self.run_id.strip():
            raise ValueError("run_id must be a nonempty string")
        if type(self.attempt_no) is not int or self.attempt_no <= 0:
            raise ValueError("attempt_no must be a positive integer")
        if self.stage != "page_transcription" or type(self.page_number) is not int or self.page_number < 1:
            raise ValueError("Invalid page cache reuse scope")
        if self.cached_status not in {"completed", "failed"}:
            raise ValueError("Unsupported cached page status")
        if self.cached_method is not None and self.cached_method not in PAGE_METHODS:
            raise ValueError("Unsupported cached page method")
        if self.cached_model is not None and (not isinstance(self.cached_model, str)
                or len(self.cached_model) > 128
                or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]*", self.cached_model) is None):
            raise ValueError("Invalid cached model")
        if self.artifact_ids is not None and (not isinstance(self.artifact_ids, (tuple, list))
                or any(not isinstance(value, str) or not value.strip() for value in self.artifact_ids)):
            raise ValueError("Invalid artifact references")

    def to_item(self):
        item = super().to_item()
        item.update(run_id=self.run_id, attempt_no=self.attempt_no, stage=self.stage,
                    page_number=self.page_number, cached_status=self.cached_status)
        if self.cached_method is not None: item["cached_method"] = self.cached_method
        if self.cached_model is not None: item["cached_model"] = self.cached_model
        if self.artifact_ids: item["artifact_ids"] = list(self.artifact_ids)
        return item

    @classmethod
    def from_item(cls, item):
        return cls(**_envelope(item), run_id=item["run_id"],
                   attempt_no=_integer(item["attempt_no"]), stage=item["stage"],
                   page_number=_integer(item["page_number"]), cached_status=item["cached_status"],
                   cached_method=item.get("cached_method"), cached_model=item.get("cached_model"),
                    artifact_ids=tuple(item["artifact_ids"]) if item.get("artifact_ids") is not None else None)


@dataclass(frozen=True)
class AttemptStarted(FileReceived):
    run_id: str
    attempt_no: int

    def __post_init__(self):
        super(AttemptStarted, self).__post_init__()
        if not isinstance(self.run_id, str) or not self.run_id.strip():
            raise ValueError("run_id must be a nonempty string")
        if type(self.attempt_no) is not int or self.attempt_no <= 0:
            raise ValueError("attempt_no must be a positive integer")

    def to_item(self) -> dict:
        item = super().to_item()
        item.update(run_id=self.run_id, attempt_no=self.attempt_no)
        return item

    @classmethod
    def from_item(cls, item: Mapping) -> "AttemptStarted":
        return cls(**_attempt_values(item))


PAGE_METHODS = frozenset({"native", "vision"})


@dataclass(frozen=True)
class PageCompleted(StepStarted):
    duration_ms: float | None = None
    method: str | None = None
    model: str | None = None

    def __post_init__(self):
        StepStarted.__post_init__(self)
        if self.stage != "page_transcription" or self.type not in {"PageCompleted", "PageFailed"}:
            raise ValueError("Unsupported page outcome")
        _duration(self.duration_ms)
        if self.method is not None and self.method not in PAGE_METHODS:
            raise ValueError("Unsupported page method")
        if self.model is not None and (self.method != "vision" or not isinstance(self.model, str)
                                       or len(self.model) > 128
                                       or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]*", self.model) is None):
            raise ValueError("model requires an observed vision method")

    def to_item(self):
        item = super().to_item()
        if self.duration_ms is not None: item["duration_ms"] = Decimal(str(self.duration_ms))
        if self.method is not None: item["method"] = self.method
        if self.model is not None: item["model"] = self.model
        return item

    @classmethod
    def from_item(cls, item):
        return cls(**_step_values(item), duration_ms=_stored_duration(item),
                   method=item.get("method"), model=item.get("model"))


@dataclass(frozen=True)
class PageFailed(PageCompleted):
    error_code: str = "PAGE_TRANSCRIPTION_FAILED"

    def __post_init__(self):
        PageCompleted.__post_init__(self)
        if self.type != "PageFailed" or self.error_code not in STEP_ERROR_CODES:
            raise ValueError("Unsupported page error code")

    def to_item(self):
        item = super().to_item()
        item["error_code"] = self.error_code
        return item

    @classmethod
    def from_item(cls, item):
        return cls(**_step_values(item), duration_ms=_stored_duration(item),
                   method=item.get("method"), model=item.get("model"), error_code=item["error_code"])


RETRY_REASON_CODES = frozenset({"MAX_ATTEMPTS", "RETRYABLE_FAILURE", "THROTTLED"})
ATTEMPT_STATUSES = frozenset({"completed", "partial", "failed"})
RUN_STATUSES = ATTEMPT_STATUSES
RUN_ERROR_CODES = STEP_ERROR_CODES | frozenset({"PROCESSING_FAILED", "RETRY_EXHAUSTED"})


def _runtime_common(event, expected_type):
    FileReceived.__post_init__(event)
    if event.type != expected_type:
        raise ValueError("Unsupported audit event type")
    if not isinstance(event.run_id, str) or not event.run_id.strip():
        raise ValueError("run_id must be a nonempty string")


def _runtime_values(item, *, attempt=False):
    values = _envelope(item)
    if attempt:
        values["attempt_no"] = _integer(item["attempt_no"])
    return values


@dataclass(frozen=True)
class RetryEnqueued(FileReceived):
    run_id: str
    attempt_no: int
    reason_code: str | None = None

    def __post_init__(self):
        _runtime_common(self, "RetryEnqueued")
        if type(self.attempt_no) is not int or self.attempt_no < 1:
            raise ValueError("attempt_no must be a positive integer")
        if self.reason_code is not None and self.reason_code not in RETRY_REASON_CODES:
            raise ValueError("Unsupported retry reason code")

    def to_item(self):
        item = super().to_item()
        item.update(run_id=self.run_id, attempt_no=self.attempt_no)
        if self.reason_code is not None: item["reason_code"] = self.reason_code
        return item

    @classmethod
    def from_item(cls, item):
        values = _runtime_values(item, attempt=True)
        return cls(**{name: values[name] for name in EVENT_FIELDS}, run_id=item["run_id"],
                   attempt_no=values["attempt_no"], reason_code=item.get("reason_code"))


@dataclass(frozen=True)
class AttemptFinished(FileReceived):
    run_id: str
    attempt_no: int
    attempt_status: str
    duration_ms: float | None = None
    error_code: str | None = None

    def __post_init__(self):
        _runtime_common(self, "AttemptFinished")
        if type(self.attempt_no) is not int or self.attempt_no < 1:
            raise ValueError("attempt_no must be a positive integer")
        if self.attempt_status not in ATTEMPT_STATUSES: raise ValueError("Unsupported attempt status")
        if self.duration_ms is not None and (isinstance(self.duration_ms, bool) or not isinstance(self.duration_ms, (int, float)) or not math.isfinite(self.duration_ms) or self.duration_ms < 0):
            raise ValueError("duration_ms must be finite and nonnegative")
        if self.error_code is not None and self.error_code not in RUN_ERROR_CODES:
            raise ValueError("Unsupported error code")

    def to_item(self):
        item = super().to_item(); item.update(run_id=self.run_id, attempt_no=self.attempt_no, attempt_status=self.attempt_status)
        if self.duration_ms is not None: item["duration_ms"] = Decimal(str(self.duration_ms))
        if self.error_code is not None: item["error_code"] = self.error_code
        return item

    @classmethod
    def from_item(cls, item):
        values = _runtime_values(item, attempt=True)
        return cls(**{name: values[name] for name in EVENT_FIELDS}, run_id=item["run_id"],
                   attempt_no=values["attempt_no"], attempt_status=item["attempt_status"],
                   duration_ms=float(item["duration_ms"]) if item.get("duration_ms") is not None else None,
                   error_code=item.get("error_code"))


@dataclass(frozen=True)
class RunFinished(FileReceived):
    run_id: str
    run_status: str
    attempt_no: int | None = None
    error_code: str | None = None

    def __post_init__(self):
        _runtime_common(self, "RunFinished")
        if self.run_status not in RUN_STATUSES: raise ValueError("Unsupported run status")
        if self.attempt_no is not None and (type(self.attempt_no) is not int or self.attempt_no < 1):
            raise ValueError("attempt_no must be a positive integer when present")
        if self.error_code is not None and self.error_code not in RUN_ERROR_CODES:
            raise ValueError("Unsupported error code")

    def to_item(self):
        item = super().to_item(); item.update(run_id=self.run_id, run_status=self.run_status)
        if self.attempt_no is not None: item["attempt_no"] = self.attempt_no
        if self.error_code is not None: item["error_code"] = self.error_code
        return item

    @classmethod
    def from_item(cls, item):
        values = _runtime_values(item, attempt="attempt_no" in item)
        return cls(**{name: values[name] for name in EVENT_FIELDS}, run_id=item["run_id"],
                   run_status=item["run_status"], attempt_no=values.get("attempt_no"),
                   error_code=item.get("error_code"))
