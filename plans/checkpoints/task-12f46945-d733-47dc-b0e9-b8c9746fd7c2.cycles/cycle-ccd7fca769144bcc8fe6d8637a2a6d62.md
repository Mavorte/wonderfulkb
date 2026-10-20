# TDD Red-Green Proof: task-12f46945-d733-47dc-b0e9-b8c9746fd7c2

<!-- proof-capture-metadata: {"version":1,"task_id":"task-12f46945-d733-47dc-b0e9-b8c9746fd7c2","command":["env","PYTHONPATH=be-document-processing/src","be-document-processing/.venv/bin/python","-m","pytest","-q","be-intake/tests/test_processing_monitor_extraction.py"],"command_sha256":"ce7cff4d09d8dea5c92fdcfc534aa704207b7ca126676396dc2a86e1b7229a67"} -->

## RED Phase
- **Timestamp:** 2026-10-20T09:53:06.549760+00:00
- **Test command:** `env PYTHONPATH=be-document-processing/src be-document-processing/.venv/bin/python -m pytest -q be-intake/tests/test_processing_monitor_extraction.py`
- **Exit code:** 1

### Standard Output
````text
FFFF                                                                     [100%]
=================================== FAILURES ===================================
________________ test_extraction_terminal_only_http_observation ________________

monitor = (<module 'intake_under_test' from '/Users/michal/Projects/wonderfulkb/be-intake/app/main.py'>, <MagicMock id='44000507...type': 'SERVICE', 'enabled': True, 'case_ids': ['case-test']}], 'retained_documents': []}, <MagicMock id='4402157216'>)

    def test_extraction_terminal_only_http_observation(monitor):
        main, _, _, _, _, table = monitor
        table.query.return_value = {"Items": [extraction()]}
        response = get(main, limit=1)
        assert response.status_code == 200
        body = response.json()
        assert body["coverage"] == "partial"
>       assert body["items"] == [{
            "event_id": "extraction-terminal", "type": "StepFinished", "sequence": 7,
            "occurred_at": "2026-10-20T10:00:00Z", "run_id": "run-test",
            "attempt_no": 1, "stage": "extraction",
        }]
E       AssertionError: assert [] == [{'event_id':...00:00Z', ...}]
E         
E         Right contains one more item: {'event_id': 'extraction-terminal', 'type': 'StepFinished', 'sequence': 7, 'occurred_at': '2026-10-20T10:00:00Z', ...}
E         Use -v to get more diff

be-intake/tests/test_processing_monitor_extraction.py:37: AssertionError
________ test_extraction_facts_parity_privacy_and_schema[StepFinished] _________

monitor = (<module 'intake_under_test' from '/Users/michal/Projects/wonderfulkb/be-intake/app/main.py'>, <MagicMock id='43248053...type': 'SERVICE', 'enabled': True, 'case_ids': ['case-test']}], 'retained_documents': []}, <MagicMock id='4403064384'>)
terminal = 'StepFinished'

    @pytest.mark.parametrize("terminal", ["StepFinished", "StepFailed", None])
    def test_extraction_facts_parity_privacy_and_schema(monitor, terminal):
        main, _, _, _, _, table = monitor
        rows = [extraction("StepStarted", "start")]
        if terminal:
            extra = {"duration_ms": Decimal("2.5")}
            if terminal == "StepFailed":
                extra["error_code"] = "EXTRACTION_FAILED"
            rows.append(extraction(terminal, "terminal", **extra))
        private = {key: "private-value" for key in (
            "fields", "quotes", "evidence", "labels", "prompt", "result", "raw_error", "counts")}
        table.query.return_value = {"Items": [dict(row, **private) for row in rows] + [
            {**extraction(), "attempt_no": 2}, {**extraction(), "run_id": "other-run"},
            {**extraction(), "stage": "source_validation", "event_id": "source"}]}
        response = get(main)
        assert response.status_code == 200
        items = response.json()["items"]
>       assert [item["event_id"] for item in items] == [row["event_id"] for row in rows] + ["source"]
E       AssertionError: assert ['source'] == ['start', 'te...al', 'source']
E         
E         At index 0 diff: 'source' != 'start'
E         Right contains 2 more items, first extra item: 'terminal'
E         Use -v to get more diff

be-intake/tests/test_processing_monitor_extraction.py:64: AssertionError
_________ test_extraction_facts_parity_privacy_and_schema[StepFailed] __________

monitor = (<module 'intake_under_test' from '/Users/michal/Projects/wonderfulkb/be-intake/app/main.py'>, <MagicMock id='44030653...type': 'SERVICE', 'enabled': True, 'case_ids': ['case-test']}], 'retained_documents': []}, <MagicMock id='4405250768'>)
terminal = 'StepFailed'

    @pytest.mark.parametrize("terminal", ["StepFinished", "StepFailed", None])
    def test_extraction_facts_parity_privacy_and_schema(monitor, terminal):
        main, _, _, _, _, table = monitor
        rows = [extraction("StepStarted", "start")]
        if terminal:
            extra = {"duration_ms": Decimal("2.5")}
            if terminal == "StepFailed":
                extra["error_code"] = "EXTRACTION_FAILED"
            rows.append(extraction(terminal, "terminal", **extra))
        private = {key: "private-value" for key in (
            "fields", "quotes", "evidence", "labels", "prompt", "result", "raw_error", "counts")}
        table.query.return_value = {"Items": [dict(row, **private) for row in rows] + [
            {**extraction(), "attempt_no": 2}, {**extraction(), "run_id": "other-run"},
            {**extraction(), "stage": "source_validation", "event_id": "source"}]}
        response = get(main)
        assert response.status_code == 200
        items = response.json()["items"]
>       assert [item["event_id"] for item in items] == [row["event_id"] for row in rows] + ["source"]
E       AssertionError: assert ['source'] == ['start', 'te...al', 'source']
E         
E         At index 0 diff: 'source' != 'start'
E         Right contains 2 more items, first extra item: 'terminal'
E         Use -v to get more diff

be-intake/tests/test_processing_monitor_extraction.py:64: AssertionError
____________ test_extraction_facts_parity_privacy_and_schema[None] _____________

monitor = (<module 'intake_under_test' from '/Users/michal/Projects/wonderfulkb/be-intake/app/main.py'>, <MagicMock id='44052517...type': 'SERVICE', 'enabled': True, 'case_ids': ['case-test']}], 'retained_documents': []}, <MagicMock id='4405257824'>)
terminal = None

    @pytest.mark.parametrize("terminal", ["StepFinished", "StepFailed", None])
    def test_extraction_facts_parity_privacy_and_schema(monitor, terminal):
        main, _, _, _, _, table = monitor
        rows = [extraction("StepStarted", "start")]
        if terminal:
            extra = {"duration_ms": Decimal("2.5")}
            if terminal == "StepFailed":
                extra["error_code"] = "EXTRACTION_FAILED"
            rows.append(extraction(terminal, "terminal", **extra))
        private = {key: "private-value" for key in (
            "fields", "quotes", "evidence", "labels", "prompt", "result", "raw_error", "counts")}
        table.query.return_value = {"Items": [dict(row, **private) for row in rows] + [
            {**extraction(), "attempt_no": 2}, {**extraction(), "run_id": "other-run"},
            {**extraction(), "stage": "source_validation", "event_id": "source"}]}
        response = get(main)
        assert response.status_code == 200
        items = response.json()["items"]
>       assert [item["event_id"] for item in items] == [row["event_id"] for row in rows] + ["source"]
E       AssertionError: assert ['source'] == ['start', 'source']
E         
E         At index 0 diff: 'source' != 'start'
E         Right contains one more item: 'source'
E         Use -v to get more diff

be-intake/tests/test_processing_monitor_extraction.py:64: AssertionError
=============================== warnings summary ===============================
be-document-processing/.venv/lib/python3.13/site-packages/fastapi/testclient.py:1
  /Users/michal/Projects/wonderfulkb/be-document-processing/.venv/lib/python3.13/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

be-intake/tests/test_processing_monitor_extraction.py:8
be-intake/tests/test_processing_monitor_extraction.py:8
  /Users/michal/Projects/wonderfulkb/be-intake/tests/test_processing_monitor_extraction.py:8: DeprecationWarning: jsonschema.RefResolver is deprecated as of v4.18.0, in favor of the https://github.com/python-jsonschema/referencing library, which provides more compliant referencing behavior as well as more flexible APIs for customization. A future release will remove RefResolver. Please file a feature request (on referencing) if you are missing an API for the kind of customization you need.
    from jsonschema import RefResolver

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
FAILED be-intake/tests/test_processing_monitor_extraction.py::test_extraction_terminal_only_http_observation
FAILED be-intake/tests/test_processing_monitor_extraction.py::test_extraction_facts_parity_privacy_and_schema[StepFinished]
FAILED be-intake/tests/test_processing_monitor_extraction.py::test_extraction_facts_parity_privacy_and_schema[StepFailed]
FAILED be-intake/tests/test_processing_monitor_extraction.py::test_extraction_facts_parity_privacy_and_schema[None]
4 failed, 3 warnings in 0.29s
````

### Standard Error
````text

````

## GREEN Phase
- **Timestamp:** 2026-10-20T09:54:08.090864+00:00
- **Test command:** `env PYTHONPATH=be-document-processing/src be-document-processing/.venv/bin/python -m pytest -q be-intake/tests/test_processing_monitor_extraction.py`
- **Exit code:** 0

### Standard Output
````text
....                                                                     [100%]
=============================== warnings summary ===============================
be-document-processing/.venv/lib/python3.13/site-packages/fastapi/testclient.py:1
  /Users/michal/Projects/wonderfulkb/be-document-processing/.venv/lib/python3.13/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

be-intake/tests/test_processing_monitor_extraction.py:8
be-intake/tests/test_processing_monitor_extraction.py:8
  /Users/michal/Projects/wonderfulkb/be-intake/tests/test_processing_monitor_extraction.py:8: DeprecationWarning: jsonschema.RefResolver is deprecated as of v4.18.0, in favor of the https://github.com/python-jsonschema/referencing library, which provides more compliant referencing behavior as well as more flexible APIs for customization. A future release will remove RefResolver. Please file a feature request (on referencing) if you are missing an API for the kind of customization you need.
    from jsonschema import RefResolver

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
4 passed, 3 warnings in 0.43s
````

### Standard Error
````text

````
