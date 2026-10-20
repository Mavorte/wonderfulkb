"""Pure summaries of a caller-supplied, finite audit observation window."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence


@dataclass(frozen=True)
class Evidence:
    event_id: object
    sequence: object
    event_type: object


@dataclass(frozen=True)
class RunObservation:
    run_id: object
    state: str
    evidence: tuple[Evidence, ...]


@dataclass(frozen=True)
class AttemptObservation:
    run_id: object
    attempt_id: object
    attempt_number: object
    terminal_state: str
    evidence: tuple[Evidence, ...]


@dataclass(frozen=True)
class PublishedResultObservation:
    run_id: object
    publication_id: object
    evidence: tuple[Evidence, ...]


@dataclass(frozen=True)
class LifecycleSummary:
    coverage: str
    next_token: object
    scope: str
    availability: str
    runs: tuple[RunObservation, ...]
    attempts: tuple[AttemptObservation, ...]
    published_results: tuple[PublishedResultObservation, ...]
    unscoped_evidence: tuple[Evidence, ...] = ()
    conflicts: tuple["IdentityConflict", ...] = ()


@dataclass(frozen=True)
class IdentityConflict:
    evidence: tuple[Evidence, ...]


_RUN_TERMINALS = {"RunFinished": "finished", "RunFailed": "failed"}
_ATTEMPT_TERMINALS = {
    "AttemptFinished": "finished",
    "AttemptFailed": "failed",
}
_ATTEMPT_STATUS = {"completed": "completed", "partial": "partial", "failed": "failed"}


def reduce_observations(
    observations: Sequence[Mapping[str, object]], *, next_token: object,
    availability: str = "unknown", availability_evidence: object = None,
    read_error: object = None,
) -> LifecycleSummary:
    """Summarize only facts present in one bounded window; never performs I/O."""
    if read_error is not None:
        raise RuntimeError(f"audit observation read failed: {read_error}")
    if availability not in {"unknown", "not_configured", "not_instrumented"}:
        raise ValueError("availability must be supported by explicit caller evidence")
    if availability != "unknown" and availability_evidence is None:
        raise ValueError("non-unknown availability requires explicit caller evidence")
    unique: list[Mapping[str, object]] = []
    by_identity: dict[tuple[object, ...], list[Mapping[str, object]]] = {}
    conflicting_items: list[Mapping[str, object]] = []
    conflicted_identities: set[tuple[object, ...]] = set()
    for item in observations:
        identity = (item.get("event_id"), item.get("sequence"))
        try:
            hash(identity)
        except TypeError:
            identity = (repr(identity),)
        if identity in conflicted_identities:
            prior = by_identity[identity]
            prior.append(item)
            conflicting_items.append(item)
            continue
        prior = by_identity.setdefault(identity, [])
        if any(dict(previous) == dict(item) for previous in prior):
            continue
        if prior:
            conflicted_identities.add(identity)
            conflicting_items.extend(prior)
            conflicting_items.append(item)
        prior.append(item)
        unique.append(item)

    def ev(item: Mapping[str, object]) -> Evidence:
        return Evidence(item.get("event_id"), item.get("sequence"), item.get("type"))

    grouped_runs: dict[object, list[Mapping[str, object]]] = {}
    grouped_attempts: dict[tuple[object, object], list[Mapping[str, object]]] = {}
    grouped_publications: dict[tuple[object, object], list[Mapping[str, object]]] = {}
    unscoped: list[Mapping[str, object]] = []
    for item in unique:
        identity = (item.get("event_id"), item.get("sequence"))
        try:
            hash(identity)
        except TypeError:
            identity = (repr(identity),)
        run_id = item.get("run_id")
        if run_id is not None:
            grouped_runs.setdefault(run_id, []).append(item)
        event_type = item.get("type")
        attempt_no = item.get("attempt_no")
        if event_type in {"AttemptFinished", "AttemptFailed"}:
            if run_id is None:
                unscoped.append(item)
                continue
            number = attempt_no
            if run_id is not None and type(number) is int and number > 0:
                grouped_attempts.setdefault((run_id, number), []).append(item)
        elif event_type == "AttemptStarted":
            canonical = item.get("attempt_no")
            legacy = item.get("attempt_number")
            number = canonical if type(canonical) is int and canonical > 0 else None
            if legacy is not None and type(legacy) is not int:
                number = None
            elif canonical is not None and legacy is not None and canonical != legacy:
                number = None
            if run_id is not None and type(number) is int and number > 0:
                grouped_attempts.setdefault((run_id, number), []).append(item)
        publication_id = item.get("publication_id")
        if publication_id is None and event_type == "ResultPublished":
            publication_id = item.get("event_id")
        if publication_id is not None:
            grouped_publications.setdefault((run_id, publication_id), []).append(item)

    runs = []
    for run_id, items in grouped_runs.items():
        terminals = {
            (item.get("run_status") or "finished") if item.get("type") == "RunFinished"
            else "failed"
            for item in items if item.get("type") in _RUN_TERMINALS
        }
        identities = {(item.get("event_id"), item.get("sequence")) for item in items}
        conflict = any(
            len({repr(dict(candidate)) for candidate in by_identity.get(identity, ())}) > 1
            for identity in identities
        )
        state = "ambiguous" if conflict or len(terminals) > 1 or any(
            value not in _ATTEMPT_STATUS and value != "finished" for value in terminals
        ) and terminals else next(iter(terminals)) if terminals else "unknown"
        runs.append(RunObservation(run_id, state, tuple(ev(item) for item in items)))

    attempts = []
    for (run_id, attempt_id), items in grouped_attempts.items():
        outcomes = set()
        invalid_status = False
        for item in items:
            if item.get("type") == "AttemptFinished":
                value = item.get("attempt_status")
                if value in _ATTEMPT_STATUS:
                    outcomes.add(value)
                else:
                    invalid_status = True
        outcomes.update(
            _ATTEMPT_TERMINALS[item.get("type")]
            for item in items
            if item.get("type") in _ATTEMPT_TERMINALS and item.get("type") != "AttemptFinished"
        )
        # AttemptFinished is a generic event kind: its explicit status is the
        # outcome. Older observations without status retain the generic fact.
        if any(item.get("type") == "AttemptFinished" and item.get("attempt_status") is None for item in items):
            outcomes.add("finished")
        conflict = any(
            len({repr(dict(candidate)) for candidate in by_identity.get((item.get("event_id"), item.get("sequence")), ())}) > 1
            for item in items
        )
        number = attempt_id
        if any(item.get("type") == "AttemptFinished" and item.get("attempt_status") is None for item in items):
            outcomes.add("finished")
        state = "ambiguous" if conflict or invalid_status or len(outcomes) > 1 else next(iter(outcomes)) if outcomes else "unknown"
        attempts.append(AttemptObservation(run_id, attempt_id, number, state, tuple(ev(item) for item in items)))

    publications = tuple(
        PublishedResultObservation(run_id, publication_id, tuple(ev(item) for item in items))
        for (run_id, publication_id), items in grouped_publications.items()
    )
    conflict_evidence = tuple(ev(item) for item in conflicting_items)
    return LifecycleSummary("partial", next_token, "provided finite observation window", availability, tuple(runs), tuple(attempts), publications,
                            tuple(ev(item) for item in unscoped),
                            (IdentityConflict(conflict_evidence),) if conflict_evidence else ())
