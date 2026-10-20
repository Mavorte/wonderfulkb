# TDD Red-Green Proof: task-ef257fc0-2159-4888-983a-0b30a1dbfe39

<!-- proof-capture-metadata: {"version":1,"task_id":"task-ef257fc0-2159-4888-983a-0b30a1dbfe39","command":["env","PYTHONPATH=be-document-processing/src","be-document-processing/.venv/bin/python","-m","pytest","-q","be-intake/tests/test_processing_monitor_authorization.py","be-document-processing/tests/test_monitor_publication_events.py"],"command_sha256":"a123521818786fed3ea1b78f31f2869ef0c0170aca03fe273d4e3e9fafce9fff"} -->

## RED Phase
- **Timestamp:** 2026-10-20T08:25:04.765871+00:00
- **Test command:** `env PYTHONPATH=be-document-processing/src be-document-processing/.venv/bin/python -m pytest -q be-intake/tests/test_processing_monitor_authorization.py be-document-processing/tests/test_monitor_publication_events.py`
- **Exit code:** 1

### Standard Output
````text
FF..FF..FFFFFFFFFF                                                       [100%]
=================================== FAILURES ===================================
_____________ test_composition_installs_real_lifecycle_authorizer ______________

intake = (<module 'intake_under_test' from '/Users/michal/Projects/wonderfulkb/be-intake/app/main.py'>, <MagicMock id='4490606448'>, <MagicMock id='4491580416'>, <MagicMock id='4491580752'>, [], [])

    def test_composition_installs_real_lifecycle_authorizer(intake):
>       assert callable(getattr(intake[0].app.state, "lifecycle_authorize_read", None))
E       AssertionError: assert False
E        +  where False = callable(None)
E        +    where None = getattr(<starlette.datastructures.State object at 0x10bc86ba0>, 'lifecycle_authorize_read', None)
E        +      where <starlette.datastructures.State object at 0x10bc86ba0> = <fastapi.applications.FastAPI object at 0x10bb83230>.state
E        +        where <fastapi.applications.FastAPI object at 0x10bb83230> = <module 'intake_under_test' from '/Users/michal/Projects/wonderfulkb/be-intake/app/main.py'>.app

be-intake/tests/test_processing_monitor_authorization.py:34: AssertionError
________ test_real_boundary_publication_routes_and_revocation[intake0] _________

intake = (<module 'intake_under_test' from '/Users/michal/Projects/wonderfulkb/be-intake/app/main.py'>, <MagicMock id='4433391504'>, <MagicMock id='4493935344'>, <MagicMock id='4493935680'>, [], [])

    @pytest.mark.parametrize("intake", [CONFIG], indirect=True)
    def test_real_boundary_publication_routes_and_revocation(intake):
        main, resource, docs = configure(intake)
        with TestClient(main.app) as client:
            for suffix in ("/runs", "/runs/run-1", "/audit"):
                response = client.get(PREFIX + suffix, headers=HEADERS)
>               assert response.status_code == 200, response.text
E               AssertionError: {"error":"case read access unavailable"}
E               assert 403 == 200
E                +  where 403 = <Response [403 Forbidden]>.status_code

be-intake/tests/test_processing_monitor_authorization.py:43: AssertionError
________ test_real_boundary_denial_before_audit[ungranted-404-intake0] _________

intake = (<module 'intake_under_test' from '/Users/michal/Projects/wonderfulkb/be-intake/app/main.py'>, <MagicMock id='4494210592'>, <MagicMock id='4494211264'>, <MagicMock id='4494211600'>, [], [])
failure = 'ungranted', code = 404

    @pytest.mark.parametrize("intake", [CONFIG], indirect=True)
    @pytest.mark.parametrize("failure,code", [("missing", 403), ("forged", 403), ("ungranted", 404),
        ("membership", 404), ("outage", 403), ("malformed", 403)])
    def test_real_boundary_denial_before_audit(intake, failure, code):
        main, resource, docs = configure(intake)
        headers, path = dict(HEADERS), PREFIX
        if failure == "missing": headers.pop("Authorization")
        if failure == "forged": headers["Authorization"] = "Bearer forged"
        if failure == "ungranted": path = path.replace("doc-test", "doc-other")
        if failure == "membership": docs.get_item.return_value["Item"]["case_id"] = "forged"
        if failure == "outage": resource.monitor_secrets.get_secret_value.side_effect = RuntimeError("offline")
        if failure == "malformed": resource.monitor_secrets.get_secret_value.return_value = {"SecretString": "{}"}
        with TestClient(main.app) as client:
            response = client.get(path + "/runs", headers=headers)
>       assert response.status_code == code
E       assert 403 == 404
E        +  where 403 = <Response [403 Forbidden]>.status_code

be-intake/tests/test_processing_monitor_authorization.py:73: AssertionError
________ test_real_boundary_denial_before_audit[membership-404-intake0] ________

intake = (<module 'intake_under_test' from '/Users/michal/Projects/wonderfulkb/be-intake/app/main.py'>, <MagicMock id='4497183072'>, <MagicMock id='4497183744'>, <MagicMock id='4497184080'>, [], [])
failure = 'membership', code = 404

    @pytest.mark.parametrize("intake", [CONFIG], indirect=True)
    @pytest.mark.parametrize("failure,code", [("missing", 403), ("forged", 403), ("ungranted", 404),
        ("membership", 404), ("outage", 403), ("malformed", 403)])
    def test_real_boundary_denial_before_audit(intake, failure, code):
        main, resource, docs = configure(intake)
        headers, path = dict(HEADERS), PREFIX
        if failure == "missing": headers.pop("Authorization")
        if failure == "forged": headers["Authorization"] = "Bearer forged"
        if failure == "ungranted": path = path.replace("doc-test", "doc-other")
        if failure == "membership": docs.get_item.return_value["Item"]["case_id"] = "forged"
        if failure == "outage": resource.monitor_secrets.get_secret_value.side_effect = RuntimeError("offline")
        if failure == "malformed": resource.monitor_secrets.get_secret_value.return_value = {"SecretString": "{}"}
        with TestClient(main.app) as client:
            response = client.get(path + "/runs", headers=headers)
>       assert response.status_code == code
E       assert 403 == 404
E        +  where 403 = <Response [403 Forbidden]>.status_code

be-intake/tests/test_processing_monitor_authorization.py:73: AssertionError
_______________ test_bounded_reader_decodes_partial_publication ________________

    def test_bounded_reader_decodes_partial_publication():
        table = Mock()
        table.query.return_value = {"Items": [row()]}
>       page = read_document(table, "case-test", "doc-test", limit=1)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

be-document-processing/tests/test_monitor_publication_events.py:20: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
be-document-processing/src/document_processing/audit/audit_queries.py:75: in read_document
    items=[_event_from_item(item) for item in response["Items"]],
           ^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

item = {'schema_version': 1, 'case_id': 'case-test', 'document_id': 'doc-test', 'event_id': 'publication-1', ...}

    def _event_from_item(item: dict):
        event_type = item.get("type")
        event_class = {
            "FileReceived": FileReceived,
            "RunQueued": RunQueued,
            "AttemptStarted": AttemptStarted,
            "RetryEnqueued": RetryEnqueued,
            "AttemptFinished": AttemptFinished,
            "RunFinished": RunFinished,
            "StepStarted": StepStarted,
            "StepFinished": StepFinished,
            "StepFailed": StepFailed,
            "PageCompleted": PageCompleted,
            "PageFailed": PageFailed,
            "PageCacheReused": PageCacheReused,
        }.get(event_type)
        if event_class is None:
>           raise ValueError("Unsupported audit event type")
E           ValueError: Unsupported audit event type

be-document-processing/src/document_processing/audit/audit_queries.py:97: ValueError
__________ test_publication_store_round_trip_and_duplicate[completed] __________

status = 'completed'

    @pytest.mark.parametrize("status", ["completed", "partial", "failed"])
    def test_publication_store_round_trip_and_duplicate(status):
>       from document_processing.audit.audit_events import ResultPublished
E       ImportError: cannot import name 'ResultPublished' from 'document_processing.audit.audit_events' (/Users/michal/Projects/wonderfulkb/be-document-processing/src/document_processing/audit/audit_events.py)

be-document-processing/tests/test_monitor_publication_events.py:27: ImportError
___________ test_publication_store_round_trip_and_duplicate[partial] ___________

status = 'partial'

    @pytest.mark.parametrize("status", ["completed", "partial", "failed"])
    def test_publication_store_round_trip_and_duplicate(status):
>       from document_processing.audit.audit_events import ResultPublished
E       ImportError: cannot import name 'ResultPublished' from 'document_processing.audit.audit_events' (/Users/michal/Projects/wonderfulkb/be-document-processing/src/document_processing/audit/audit_events.py)

be-document-processing/tests/test_monitor_publication_events.py:27: ImportError
___________ test_publication_store_round_trip_and_duplicate[failed] ____________

status = 'failed'

    @pytest.mark.parametrize("status", ["completed", "partial", "failed"])
    def test_publication_store_round_trip_and_duplicate(status):
>       from document_processing.audit.audit_events import ResultPublished
E       ImportError: cannot import name 'ResultPublished' from 'document_processing.audit.audit_events' (/Users/michal/Projects/wonderfulkb/be-document-processing/src/document_processing/audit/audit_events.py)

be-document-processing/tests/test_monitor_publication_events.py:27: ImportError
_________ test_publication_rejects_invalid_scope_or_content[changes0] __________

changes = {'result_status': 'success'}

    @pytest.mark.parametrize("changes", [{"result_status": "success"}, {"attempt_no": 0},
        {"run_id": ""}, {"artifact_ids": ["https://secret"]}, {"result": "private content"}, {"page_number": 1}])
    def test_publication_rejects_invalid_scope_or_content(changes):
>       from document_processing.audit.audit_events import ResultPublished
E       ImportError: cannot import name 'ResultPublished' from 'document_processing.audit.audit_events' (/Users/michal/Projects/wonderfulkb/be-document-processing/src/document_processing/audit/audit_events.py)

be-document-processing/tests/test_monitor_publication_events.py:43: ImportError
_________ test_publication_rejects_invalid_scope_or_content[changes1] __________

changes = {'attempt_no': 0}

    @pytest.mark.parametrize("changes", [{"result_status": "success"}, {"attempt_no": 0},
        {"run_id": ""}, {"artifact_ids": ["https://secret"]}, {"result": "private content"}, {"page_number": 1}])
    def test_publication_rejects_invalid_scope_or_content(changes):
>       from document_processing.audit.audit_events import ResultPublished
E       ImportError: cannot import name 'ResultPublished' from 'document_processing.audit.audit_events' (/Users/michal/Projects/wonderfulkb/be-document-processing/src/document_processing/audit/audit_events.py)

be-document-processing/tests/test_monitor_publication_events.py:43: ImportError
_________ test_publication_rejects_invalid_scope_or_content[changes2] __________

changes = {'run_id': ''}

    @pytest.mark.parametrize("changes", [{"result_status": "success"}, {"attempt_no": 0},
        {"run_id": ""}, {"artifact_ids": ["https://secret"]}, {"result": "private content"}, {"page_number": 1}])
    def test_publication_rejects_invalid_scope_or_content(changes):
>       from document_processing.audit.audit_events import ResultPublished
E       ImportError: cannot import name 'ResultPublished' from 'document_processing.audit.audit_events' (/Users/michal/Projects/wonderfulkb/be-document-processing/src/document_processing/audit/audit_events.py)

be-document-processing/tests/test_monitor_publication_events.py:43: ImportError
_________ test_publication_rejects_invalid_scope_or_content[changes3] __________

changes = {'artifact_ids': ['https://secret']}

    @pytest.mark.parametrize("changes", [{"result_status": "success"}, {"attempt_no": 0},
        {"run_id": ""}, {"artifact_ids": ["https://secret"]}, {"result": "private content"}, {"page_number": 1}])
    def test_publication_rejects_invalid_scope_or_content(changes):
>       from document_processing.audit.audit_events import ResultPublished
E       ImportError: cannot import name 'ResultPublished' from 'document_processing.audit.audit_events' (/Users/michal/Projects/wonderfulkb/be-document-processing/src/document_processing/audit/audit_events.py)

be-document-processing/tests/test_monitor_publication_events.py:43: ImportError
_________ test_publication_rejects_invalid_scope_or_content[changes4] __________

changes = {'result': 'private content'}

    @pytest.mark.parametrize("changes", [{"result_status": "success"}, {"attempt_no": 0},
        {"run_id": ""}, {"artifact_ids": ["https://secret"]}, {"result": "private content"}, {"page_number": 1}])
    def test_publication_rejects_invalid_scope_or_content(changes):
>       from document_processing.audit.audit_events import ResultPublished
E       ImportError: cannot import name 'ResultPublished' from 'document_processing.audit.audit_events' (/Users/michal/Projects/wonderfulkb/be-document-processing/src/document_processing/audit/audit_events.py)

be-document-processing/tests/test_monitor_publication_events.py:43: ImportError
_________ test_publication_rejects_invalid_scope_or_content[changes5] __________

changes = {'page_number': 1}

    @pytest.mark.parametrize("changes", [{"result_status": "success"}, {"attempt_no": 0},
        {"run_id": ""}, {"artifact_ids": ["https://secret"]}, {"result": "private content"}, {"page_number": 1}])
    def test_publication_rejects_invalid_scope_or_content(changes):
>       from document_processing.audit.audit_events import ResultPublished
E       ImportError: cannot import name 'ResultPublished' from 'document_processing.audit.audit_events' (/Users/michal/Projects/wonderfulkb/be-document-processing/src/document_processing/audit/audit_events.py)

be-document-processing/tests/test_monitor_publication_events.py:43: ImportError
=============================== warnings summary ===============================
<frozen importlib._bootstrap>:488
<frozen importlib._bootstrap>:488
  <frozen importlib._bootstrap>:488: DeprecationWarning: builtin type SwigPyPacked has no __module__ attribute

<frozen importlib._bootstrap>:488
<frozen importlib._bootstrap>:488
  <frozen importlib._bootstrap>:488: DeprecationWarning: builtin type SwigPyObject has no __module__ attribute

<frozen importlib._bootstrap>:488
  <frozen importlib._bootstrap>:488: DeprecationWarning: builtin type swigvarlink has no __module__ attribute

be-document-processing/.venv/lib/python3.13/site-packages/fastapi/testclient.py:1
  /Users/michal/Projects/wonderfulkb/be-document-processing/.venv/lib/python3.13/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
FAILED be-document-processing::test_composition_installs_real_lifecycle_authorizer
FAILED be-document-processing::test_real_boundary_publication_routes_and_revocation[intake0]
FAILED be-document-processing::test_real_boundary_denial_before_audit[ungranted-404-intake0]
FAILED be-document-processing::test_real_boundary_denial_before_audit[membership-404-intake0]
FAILED be-document-processing/tests/test_monitor_publication_events.py::test_bounded_reader_decodes_partial_publication
FAILED be-document-processing/tests/test_monitor_publication_events.py::test_publication_store_round_trip_and_duplicate[completed]
FAILED be-document-processing/tests/test_monitor_publication_events.py::test_publication_store_round_trip_and_duplicate[partial]
FAILED be-document-processing/tests/test_monitor_publication_events.py::test_publication_store_round_trip_and_duplicate[failed]
FAILED be-document-processing/tests/test_monitor_publication_events.py::test_publication_rejects_invalid_scope_or_content[changes0]
FAILED be-document-processing/tests/test_monitor_publication_events.py::test_publication_rejects_invalid_scope_or_content[changes1]
FAILED be-document-processing/tests/test_monitor_publication_events.py::test_publication_rejects_invalid_scope_or_content[changes2]
FAILED be-document-processing/tests/test_monitor_publication_events.py::test_publication_rejects_invalid_scope_or_content[changes3]
FAILED be-document-processing/tests/test_monitor_publication_events.py::test_publication_rejects_invalid_scope_or_content[changes4]
FAILED be-document-processing/tests/test_monitor_publication_events.py::test_publication_rejects_invalid_scope_or_content[changes5]
14 failed, 4 passed, 6 warnings in 0.22s
````

### Standard Error
````text
<sys>:0: DeprecationWarning: builtin type swigvarlink has no __module__ attribute
````

## GREEN Phase
- **Timestamp:** 2026-10-20T08:29:42.603014+00:00
- **Test command:** `env PYTHONPATH=be-document-processing/src be-document-processing/.venv/bin/python -m pytest -q be-intake/tests/test_processing_monitor_authorization.py be-document-processing/tests/test_monitor_publication_events.py`
- **Exit code:** 0

### Standard Output
````text
.....................                                                    [100%]
=============================== warnings summary ===============================
<frozen importlib._bootstrap>:488
<frozen importlib._bootstrap>:488
  <frozen importlib._bootstrap>:488: DeprecationWarning: builtin type SwigPyPacked has no __module__ attribute

<frozen importlib._bootstrap>:488
<frozen importlib._bootstrap>:488
  <frozen importlib._bootstrap>:488: DeprecationWarning: builtin type SwigPyObject has no __module__ attribute

<frozen importlib._bootstrap>:488
  <frozen importlib._bootstrap>:488: DeprecationWarning: builtin type swigvarlink has no __module__ attribute

be-document-processing/.venv/lib/python3.13/site-packages/fastapi/testclient.py:1
  /Users/michal/Projects/wonderfulkb/be-document-processing/.venv/lib/python3.13/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
21 passed, 6 warnings in 0.20s
````

### Standard Error
````text
<sys>:0: DeprecationWarning: builtin type swigvarlink has no __module__ attribute
````
