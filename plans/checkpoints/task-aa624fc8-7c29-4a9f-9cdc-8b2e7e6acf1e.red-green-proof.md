# TDD Red-Green Proof: task-aa624fc8-7c29-4a9f-9cdc-8b2e7e6acf1e

<!-- proof-capture-metadata: {"version":1,"task_id":"task-aa624fc8-7c29-4a9f-9cdc-8b2e7e6acf1e","command":["/tmp/wkb-signature-venv/bin/python","-m","pytest","be-document-processing/tests/test_monitor_signature_events.py","-q"],"command_sha256":"0bdffd87e0cd71989f51a7966c98414916eaa68473d5352cc0943256739c8457"} -->

## RED Phase
- **Timestamp:** 2026-10-20T08:44:23.193315+00:00
- **Test command:** `/tmp/wkb-signature-venv/bin/python -m pytest be-document-processing/tests/test_monitor_signature_events.py -q`
- **Exit code:** 1

### Standard Output
````text
FFFFF..F                                                                 [100%]
=================================== FAILURES ===================================
_________________ test_signature_detection_completed_roundtrip _________________

audit_table = dynamodb.Table(name='audit-signature-test')

    def test_signature_detection_completed_roundtrip(audit_table):
        store = AuditStore(audit_table)
>       started = _event(StepStarted, "sig-start-1", 1)
                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

be-document-processing/tests/test_monitor_signature_events.py:29: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
be-document-processing/tests/test_monitor_signature_events.py:22: in _event
    return cls(schema_version=1, event_id=event_id, case_id="case-1", document_id="doc-1",
<string>:14: in __init__
    ???
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

self = StepStarted(schema_version=1, event_id='sig-start-1', case_id='case-1', document_id='doc-1', sequence=1, type='StepStarted', occurred_at='2026-10-20T12:00:00Z', run_id='run-1', attempt_no=1, stage='signature_detection', page_number=None)

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
>           raise ValueError("Unsupported audit step")
E           ValueError: Unsupported audit step

be-document-processing/src/document_processing/audit/audit_events.py:181: ValueError
__________________ test_signature_terminal_only_and_duplicate __________________

audit_table = dynamodb.Table(name='audit-signature-test')

    def test_signature_terminal_only_and_duplicate(audit_table):
        store = AuditStore(audit_table)
>       finished = _event(StepFinished, "terminal", 7, duration_ms=0)
                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

be-document-processing/tests/test_monitor_signature_events.py:41: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
be-document-processing/tests/test_monitor_signature_events.py:22: in _event
    return cls(schema_version=1, event_id=event_id, case_id="case-1", document_id="doc-1",
<string>:15: in __init__
    ???
be-document-processing/src/document_processing/audit/audit_events.py:199: in __post_init__
    StepStarted.__post_init__(self)
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

self = StepFinished(schema_version=1, event_id='terminal', case_id='case-1', document_id='doc-1', sequence=7, type='StepFinis..._at='2026-10-20T12:00:00Z', run_id='run-1', attempt_no=1, stage='signature_detection', page_number=None, duration_ms=0)

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
>           raise ValueError("Unsupported audit step")
E           ValueError: Unsupported audit step

be-document-processing/src/document_processing/audit/audit_events.py:181: ValueError
______ test_invalid_signature_events_rejected_without_mutation[changes0] _______

audit_table = dynamodb.Table(name='audit-signature-test')
changes = {'stage': 'other'}

    @pytest.mark.parametrize("changes", [
        {"stage": "other"}, {"run_id": ""}, {"attempt_no": 0},
        {"duration_ms": -1}, {"duration_ms": float("inf")},
        {"signature": "secret"},
    ])
    def test_invalid_signature_events_rejected_without_mutation(audit_table, changes):
        store = AuditStore(audit_table)
        values = dict(event_id="invalid", sequence=1, duration_ms=1)
        values.update(changes)
        with pytest.raises(ValueError):
>           _event(StepFinished, values.pop("event_id"), values.pop("sequence"), **values)

be-document-processing/tests/test_monitor_signature_events.py:57: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

cls = <class 'document_processing.audit.audit_events.StepFinished'>
event_id = 'invalid', sequence = 1, extra = {'duration_ms': 1, 'stage': 'other'}

    def _event(cls, event_id, sequence, **extra):
>       return cls(schema_version=1, event_id=event_id, case_id="case-1", document_id="doc-1",
                   sequence=sequence, type=cls.__name__, occurred_at="2026-10-20T12:00:00Z",
                   run_id="run-1", attempt_no=1, stage="signature_detection", **extra)
E       TypeError: document_processing.audit.audit_events.StepFinished() got multiple values for keyword argument 'stage'

be-document-processing/tests/test_monitor_signature_events.py:22: TypeError
______ test_invalid_signature_events_rejected_without_mutation[changes1] _______

audit_table = dynamodb.Table(name='audit-signature-test')
changes = {'run_id': ''}

    @pytest.mark.parametrize("changes", [
        {"stage": "other"}, {"run_id": ""}, {"attempt_no": 0},
        {"duration_ms": -1}, {"duration_ms": float("inf")},
        {"signature": "secret"},
    ])
    def test_invalid_signature_events_rejected_without_mutation(audit_table, changes):
        store = AuditStore(audit_table)
        values = dict(event_id="invalid", sequence=1, duration_ms=1)
        values.update(changes)
        with pytest.raises(ValueError):
>           _event(StepFinished, values.pop("event_id"), values.pop("sequence"), **values)

be-document-processing/tests/test_monitor_signature_events.py:57: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

cls = <class 'document_processing.audit.audit_events.StepFinished'>
event_id = 'invalid', sequence = 1, extra = {'duration_ms': 1, 'run_id': ''}

    def _event(cls, event_id, sequence, **extra):
>       return cls(schema_version=1, event_id=event_id, case_id="case-1", document_id="doc-1",
                   sequence=sequence, type=cls.__name__, occurred_at="2026-10-20T12:00:00Z",
                   run_id="run-1", attempt_no=1, stage="signature_detection", **extra)
E       TypeError: document_processing.audit.audit_events.StepFinished() got multiple values for keyword argument 'run_id'

be-document-processing/tests/test_monitor_signature_events.py:22: TypeError
______ test_invalid_signature_events_rejected_without_mutation[changes2] _______

audit_table = dynamodb.Table(name='audit-signature-test')
changes = {'attempt_no': 0}

    @pytest.mark.parametrize("changes", [
        {"stage": "other"}, {"run_id": ""}, {"attempt_no": 0},
        {"duration_ms": -1}, {"duration_ms": float("inf")},
        {"signature": "secret"},
    ])
    def test_invalid_signature_events_rejected_without_mutation(audit_table, changes):
        store = AuditStore(audit_table)
        values = dict(event_id="invalid", sequence=1, duration_ms=1)
        values.update(changes)
        with pytest.raises(ValueError):
>           _event(StepFinished, values.pop("event_id"), values.pop("sequence"), **values)

be-document-processing/tests/test_monitor_signature_events.py:57: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

cls = <class 'document_processing.audit.audit_events.StepFinished'>
event_id = 'invalid', sequence = 1, extra = {'duration_ms': 1, 'attempt_no': 0}

    def _event(cls, event_id, sequence, **extra):
>       return cls(schema_version=1, event_id=event_id, case_id="case-1", document_id="doc-1",
                   sequence=sequence, type=cls.__name__, occurred_at="2026-10-20T12:00:00Z",
                   run_id="run-1", attempt_no=1, stage="signature_detection", **extra)
E       TypeError: document_processing.audit.audit_events.StepFinished() got multiple values for keyword argument 'attempt_no'

be-document-processing/tests/test_monitor_signature_events.py:22: TypeError
______ test_invalid_signature_events_rejected_without_mutation[changes5] _______

audit_table = dynamodb.Table(name='audit-signature-test')
changes = {'signature': 'secret'}

    @pytest.mark.parametrize("changes", [
        {"stage": "other"}, {"run_id": ""}, {"attempt_no": 0},
        {"duration_ms": -1}, {"duration_ms": float("inf")},
        {"signature": "secret"},
    ])
    def test_invalid_signature_events_rejected_without_mutation(audit_table, changes):
        store = AuditStore(audit_table)
        values = dict(event_id="invalid", sequence=1, duration_ms=1)
        values.update(changes)
        with pytest.raises(ValueError):
>           _event(StepFinished, values.pop("event_id"), values.pop("sequence"), **values)

be-document-processing/tests/test_monitor_signature_events.py:57: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

cls = <class 'document_processing.audit.audit_events.StepFinished'>
event_id = 'invalid', sequence = 1
extra = {'duration_ms': 1, 'signature': 'secret'}

    def _event(cls, event_id, sequence, **extra):
>       return cls(schema_version=1, event_id=event_id, case_id="case-1", document_id="doc-1",
                   sequence=sequence, type=cls.__name__, occurred_at="2026-10-20T12:00:00Z",
                   run_id="run-1", attempt_no=1, stage="signature_detection", **extra)
E       TypeError: StepFinished.__init__() got an unexpected keyword argument 'signature'

be-document-processing/tests/test_monitor_signature_events.py:22: TypeError
=============================== warnings summary ===============================
<frozen importlib._bootstrap>:491
<frozen importlib._bootstrap>:491
  <frozen importlib._bootstrap>:491: DeprecationWarning: builtin type SwigPyPacked has no __module__ attribute

<frozen importlib._bootstrap>:491
<frozen importlib._bootstrap>:491
  <frozen importlib._bootstrap>:491: DeprecationWarning: builtin type SwigPyObject has no __module__ attribute

<frozen importlib._bootstrap>:491
  <frozen importlib._bootstrap>:491: DeprecationWarning: builtin type swigvarlink has no __module__ attribute

../../../../private/tmp/wkb-signature-venv/lib/python3.14/site-packages/fastapi/testclient.py:1
  /private/tmp/wkb-signature-venv/lib/python3.14/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
FAILED be-document-processing/tests/test_monitor_signature_events.py::test_signature_detection_completed_roundtrip
FAILED be-document-processing/tests/test_monitor_signature_events.py::test_signature_terminal_only_and_duplicate
FAILED be-document-processing/tests/test_monitor_signature_events.py::test_invalid_signature_events_rejected_without_mutation[changes0]
FAILED be-document-processing/tests/test_monitor_signature_events.py::test_invalid_signature_events_rejected_without_mutation[changes1]
FAILED be-document-processing/tests/test_monitor_signature_events.py::test_invalid_signature_events_rejected_without_mutation[changes2]
FAILED be-document-processing/tests/test_monitor_signature_events.py::test_invalid_signature_events_rejected_without_mutation[changes5]
6 failed, 2 passed, 6 warnings in 3.12s
````

### Standard Error
````text
<sys>:0: DeprecationWarning: builtin type swigvarlink has no __module__ attribute
````

## GREEN Phase
- **Timestamp:** 2026-10-20T08:45:00.580029+00:00
- **Test command:** `/tmp/wkb-signature-venv/bin/python -m pytest be-document-processing/tests/test_monitor_signature_events.py -q`
- **Exit code:** 0

### Standard Output
````text
.......                                                                  [100%]
=============================== warnings summary ===============================
<frozen importlib._bootstrap>:491
<frozen importlib._bootstrap>:491
  <frozen importlib._bootstrap>:491: DeprecationWarning: builtin type SwigPyPacked has no __module__ attribute

<frozen importlib._bootstrap>:491
<frozen importlib._bootstrap>:491
  <frozen importlib._bootstrap>:491: DeprecationWarning: builtin type SwigPyObject has no __module__ attribute

<frozen importlib._bootstrap>:491
  <frozen importlib._bootstrap>:491: DeprecationWarning: builtin type swigvarlink has no __module__ attribute

../../../../private/tmp/wkb-signature-venv/lib/python3.14/site-packages/fastapi/testclient.py:1
  /private/tmp/wkb-signature-venv/lib/python3.14/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
7 passed, 6 warnings in 0.61s
````

### Standard Error
````text
<sys>:0: DeprecationWarning: builtin type swigvarlink has no __module__ attribute
````
