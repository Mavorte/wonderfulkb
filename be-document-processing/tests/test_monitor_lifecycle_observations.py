from document_processing.audit import audit_lifecycle_observations as lifecycle


def event(event_id, event_type, sequence, **fields):
    return {
        "schema_version": 1,
        "event_id": event_id,
        "case_id": "case-1",
        "document_id": "doc-1",
        "sequence": sequence,
        "type": event_type,
        "occurred_at": f"2026-10-20T12:00:{sequence:02d}Z",
        **fields,
    }


def test_empty_window_is_partial_and_preserves_opaque_continuation():
    token = object()
    result = lifecycle.reduce_observations([], next_token=token)
    assert result.coverage == "partial"
    assert result.next_token is token
    assert result.runs == ()
    assert result.attempts == ()
    assert result.published_results == ()


def test_retry_and_partial_publication_do_not_claim_terminal_state():
    observations = [
        event("q", "RunQueued", 1, run_id="run-1"),
        event("s1", "AttemptStarted", 2, run_id="run-1", attempt_no=1),
        event("r", "RetryEnqueued", 3, run_id="run-1", attempt_id="a1"),
        event("s2", "AttemptStarted", 4, run_id="run-1", attempt_no=2),
        event("p", "ResultPublished", 5, run_id="run-1", publication_id="pub-1"),
    ]
    result = lifecycle.reduce_observations(observations, next_token="cursor")
    assert result.coverage == "partial"
    assert len(result.runs) == 1
    assert result.runs[0].state == "unknown"
    assert {e.event_id for e in result.runs[0].evidence} == {"q", "s1", "r", "s2", "p"}
    assert len(result.attempts) == 2
    assert all(attempt.terminal_state == "unknown" for attempt in result.attempts)
    assert len(result.published_results) == 1
    assert result.next_token == "cursor"


def test_run_terminal_without_attempt_is_observed_not_synthesized():
    result = lifecycle.reduce_observations(
        [event("f", "RunFinished", 7, run_id="run-2")], next_token=None
    )
    assert len(result.runs) == 1
    assert result.runs[0].state == "finished"
    assert result.attempts == ()


def test_conflicting_run_terminals_remain_ambiguous_and_evidence_is_retained():
    observations = [
        event("f", "RunFinished", 7, run_id="run-3"),
        event("x", "RunFailed", 8, run_id="run-3"),
    ]
    result = lifecycle.reduce_observations(observations, next_token=None)
    assert result.runs[0].state == "ambiguous"
    assert {e.event_id for e in result.runs[0].evidence} == {"f", "x"}


def test_duplicate_identity_is_not_double_counted_but_distinct_observations_are():
    first = event("s", "AttemptStarted", 2, run_id="run-4", attempt_no=1)
    duplicate = dict(first)
    result = lifecycle.reduce_observations([first, duplicate], next_token=None)
    assert len(result.attempts) == 1
    assert len(result.attempts[0].evidence) == 1


def test_orphan_attempt_and_terminal_only_attempt_remain_observed():
    result = lifecycle.reduce_observations(
        [
            event("s", "AttemptStarted", 2, run_id="r", attempt_no=1),
            event("t", "AttemptFinished", 3, run_id="r", attempt_no=1, attempt_status="failed"),
        ],
        next_token=None,
    )
    assert len(result.attempts) == 1
    assert {e.event_id for e in result.attempts[0].evidence} == {"s", "t"}
    assert result.runs[0].state == "unknown"


def test_canonical_attempt_finished_groups_by_attempt_no_and_status():
    result = lifecycle.reduce_observations(
        [event("t", "AttemptFinished", 3, run_id="r", attempt_no=1, attempt_status="failed")],
        next_token=None,
    )
    assert len(result.attempts) == 1
    assert result.attempts[0].attempt_number == 1
    assert result.attempts[0].terminal_state == "failed"
    assert result.runs[0].state == "unknown"


def test_finished_terminal_and_matching_historical_status_are_consistent():
    result = lifecycle.reduce_observations(
        [event("t", "AttemptFinished", 3, run_id="r", attempt_no=1, attempt_status="completed")],
        next_token=None,
    )
    assert result.attempts[0].terminal_state == "completed"


def test_conflicting_attempt_terminal_statuses_are_ambiguous_with_evidence():
    result = lifecycle.reduce_observations(
        [
            event("t1", "AttemptFinished", 3, run_id="r", attempt_no=1, attempt_status="completed"),
            event("t2", "AttemptFinished", 4, run_id="r", attempt_no=1, attempt_status="failed"),
        ],
        next_token=None,
    )
    assert result.attempts[0].terminal_state == "ambiguous"
    assert {e.event_id for e in result.attempts[0].evidence} == {"t1", "t2"}


def test_attempt_identity_does_not_merge_distinct_runs_or_numbers():
    result = lifecycle.reduce_observations(
        [
            event("a", "AttemptFinished", 2, run_id="r1", attempt_no=1, attempt_status="failed"),
            event("b", "AttemptFinished", 3, run_id="r2", attempt_no=1, attempt_status="partial"),
            event("c", "AttemptFinished", 4, run_id="r1", attempt_no=2, attempt_status="completed"),
        ],
        next_token=None,
    )
    assert {(a.run_id, a.attempt_number, a.terminal_state) for a in result.attempts} == {
        ("r1", 1, "failed"), ("r2", 1, "partial"), ("r1", 2, "completed")
    }


def test_duplicate_identity_and_reordered_fragments_retain_bounded_evidence():
    start = event("s", "AttemptStarted", 5, run_id="r", attempt_no=1)
    terminal = event("t", "AttemptFinished", 2, run_id="r", attempt_no=1, attempt_status="completed")
    result = lifecycle.reduce_observations([terminal, start, dict(terminal)], next_token="opaque")
    assert len(result.attempts) == 1
    assert result.attempts[0].terminal_state == "completed"
    assert {e.event_id for e in result.attempts[0].evidence} == {"s", "t"}
    assert result.next_token == "opaque"
    assert result.coverage == "partial"


def test_explicit_availability_values_are_distinct_and_invalid_values_rejected():
    for availability in ("not_configured", "not_instrumented", "unknown"):
        evidence = {"source": "caller"} if availability != "unknown" else None
        assert lifecycle.reduce_observations(
            [], next_token=None, availability=availability, availability_evidence=evidence
        ).availability == availability
    try:
        lifecycle.reduce_observations([], next_token=None, availability="read_failure")
    except ValueError:
        pass
    else:
        raise AssertionError("unsupported availability must be rejected")


def test_run_finished_preserves_canonical_run_status():
    result = lifecycle.reduce_observations(
        [event("r", "RunFinished", 1, run_id="run-1", run_status="partial")],
        next_token="cursor",
    )
    assert result.runs[0].state == "partial"


def test_conflicting_payload_for_same_identity_is_retained_as_ambiguous():
    first = event("r", "RunFinished", 1, run_id="run-1", run_status="completed")
    conflict = event("r", "RunFinished", 1, run_id="run-1", run_status="failed")
    for observations in ([first, conflict], [conflict, first]):
        result = lifecycle.reduce_observations(observations, next_token=None)
        assert result.runs[0].state == "ambiguous"
        assert len(result.runs[0].evidence) == 2


def test_run_terminal_attempt_number_does_not_create_attempt():
    result = lifecycle.reduce_observations(
        [event("r", "RunFinished", 1, run_id="run-1", run_status="completed", attempt_no=3)],
        next_token=None,
    )
    assert result.attempts == ()


def test_missing_or_invalid_canonical_attempt_scope_is_not_summarized_as_definite():
    result = lifecycle.reduce_observations(
        [event("t", "AttemptFinished", 1, run_id="run-1", attempt_status="failed")],
        next_token=None,
    )
    assert result.attempts == ()


def test_non_unknown_availability_requires_explicit_caller_evidence():
    try:
        lifecycle.reduce_observations([], next_token=None, availability="not_configured")
    except ValueError:
        pass
    else:
        raise AssertionError("availability requires explicit caller evidence")


def test_read_failure_has_explicit_error_result():
    try:
        lifecycle.reduce_observations([], next_token=None, read_error="query unavailable")
    except TypeError:
        raise AssertionError("read failure needs an explicit reducer contract")
    except ValueError:
        pass
    except RuntimeError:
        pass
    else:
        raise AssertionError("read failure must not return an empty success")


def test_unscoped_attempt_terminal_is_retained_without_inventing_run():
    terminal = event("t", "AttemptFinished", 3, attempt_no=1, attempt_status="failed")
    result = lifecycle.reduce_observations([terminal], next_token="cursor")
    assert result.runs == ()
    assert result.attempts == ()
    assert result.unscoped_evidence == (lifecycle.Evidence("t", 3, "AttemptFinished"),)
    assert result.coverage == "partial" and result.next_token == "cursor"


def test_contradictory_started_ordinals_do_not_select_legacy_number():
    started = event("s", "AttemptStarted", 2, run_id="r", attempt_no=1, attempt_number=2)
    result = lifecycle.reduce_observations([started], next_token=None)
    assert result.attempts == ()


def test_same_event_identity_conflict_across_attempt_scope_is_order_independent():
    first = event("t", "AttemptFinished", 3, run_id="r", attempt_no=1, attempt_status="failed")
    conflict = event("t", "AttemptFinished", 3, run_id="r", attempt_no=2, attempt_status="failed")
    for observations in ([first, conflict], [conflict, first]):
        result = lifecycle.reduce_observations(observations, next_token="opaque")
        assert result.coverage == "partial" and result.next_token == "opaque"
        assert len(result.conflicts) == 1
        assert len(result.conflicts[0].evidence) == 2


def test_distinct_event_ids_for_different_attempt_numbers_are_independent():
    result = lifecycle.reduce_observations(
        [
            event("t1", "AttemptFinished", 3, run_id="r", attempt_no=1, attempt_status="failed"),
            event("t2", "AttemptFinished", 4, run_id="r", attempt_no=2, attempt_status="completed"),
        ], next_token=None
    )
    assert {(a.attempt_number, a.terminal_state) for a in result.attempts} == {
        (1, "failed"), (2, "completed")
    }


def test_started_legacy_attempt_number_does_not_establish_attempt_ordinal():
    started = event("s", "AttemptStarted", 2, run_id="r", attempt_number=1)
    result = lifecycle.reduce_observations([started], next_token=None)
    assert result.attempts == ()


def test_finished_legacy_attempt_number_does_not_establish_attempt_ordinal():
    finished = event(
        "f", "AttemptFinished", 3, run_id="r", attempt_number=1,
        attempt_status="failed"
    )
    result = lifecycle.reduce_observations([finished], next_token=None)
    assert result.attempts == ()
