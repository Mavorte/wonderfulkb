"""Pure mapping of a bounded window of page audit observations."""

from collections.abc import Mapping, Sequence
from copy import deepcopy


_COMMON_FIELDS = (
    "event_id", "type", "sequence", "occurred_at", "run_id", "attempt_no",
    "page_number", "stage",
)
_FIELDS_BY_TYPE = {
    "StepStarted": _COMMON_FIELDS,
    "PageCompleted": _COMMON_FIELDS + ("duration_ms", "method", "model"),
    "PageFailed": _COMMON_FIELDS + ("duration_ms", "method", "model", "error_code"),
    "PageCacheReused": _COMMON_FIELDS + (
        "cached_status", "cached_method", "cached_model", "artifact_ids",
    ),
}


def to_page_observations(
    observations: Sequence[Mapping[str, object]], *, run_id: str, attempt_no: int
) -> list[dict[str, object]]:
    """Return fresh, allowlisted page fragments for one explicit run attempt."""
    if not isinstance(run_id, str) or not run_id.strip():
        raise ValueError("run_id must be a nonempty string")
    if type(attempt_no) is not int or attempt_no < 1:
        raise ValueError("attempt_no must be a positive integer")
    if isinstance(observations, (str, bytes)) or not isinstance(observations, Sequence):
        raise TypeError("observations must be a finite sequence of mappings")

    result = []
    for observation in observations:
        if not isinstance(observation, Mapping):
            raise TypeError("each observation must be a mapping")
        observed_run = observation.get("run_id")
        observed_attempt = observation.get("attempt_no")
        if not isinstance(observed_run, str) or not observed_run.strip():
            raise ValueError("observation run_id must be a nonempty string")
        if type(observed_attempt) is not int or observed_attempt < 1:
            raise ValueError("observation attempt_no must be a positive integer")
        if observed_run != run_id or observed_attempt != attempt_no:
            continue

        event_type = observation.get("type")
        allowed = _FIELDS_BY_TYPE.get(event_type) if isinstance(event_type, str) else None
        if allowed is None:
            continue
        if event_type == "StepStarted" and observation.get("stage") != "page_transcription":
            continue
        if event_type != "StepStarted" and observation.get("stage") != "page_transcription":
            continue
        result.append({key: deepcopy(observation[key]) for key in allowed if key in observation})
    return result
