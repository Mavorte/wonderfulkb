"""Immutable owner-issued identity for one committed processing claim."""
from dataclasses import dataclass


@dataclass(frozen=True)
class ExecutionContext:
    case_id: str
    document_id: str
    run_id: str
    generation: int
    attempt_no: int
    claim_token: str


class EnqueueResult(str):
    def __new__(cls, status, run_id=None, generation=None, send_status=None):
        obj = super().__new__(cls, status)
        obj.run_id, obj.generation, obj.send_status = run_id, generation, send_status
        return obj


class ClaimResult(str):
    def __new__(cls, status, execution_context=None):
        obj = super().__new__(cls, status)
        obj.execution_context = execution_context
        obj.attempt_no = execution_context.attempt_no if execution_context else None
        return obj
