# TDD Red-Green Proof: task-0e56cd5e-0911-4acb-bcf6-4df33a97a46c

<!-- proof-capture-metadata: {"version":1,"task_id":"task-0e56cd5e-0911-4acb-bcf6-4df33a97a46c","command":["be-document-processing/.venv/bin/python","-m","pytest","-q","be-intake/tests/test_processing_monitor_cache_reused.py"],"command_sha256":"fde3bf827d97d951bcce3540d234b901b4f81bbb0ed26aae6c584feeb0450caf"} -->

## RED Phase
- **Timestamp:** 2026-10-20T09:49:34.078628+00:00
- **Test command:** `be-document-processing/.venv/bin/python -m pytest -q be-intake/tests/test_processing_monitor_cache_reused.py`
- **Exit code:** 1

### Standard Output
````text
FFFFF.......                                                             [100%]
=================================== FAILURES ===================================
_ test_reuse_fragment_survives_pages_and_document_events[completed-stored-model] _

monitor = (<module 'intake_under_test' from '/Users/michal/Projects/wonderfulkb/be-intake/app/main.py'>, <MagicMock id='45826995...type': 'SERVICE', 'enabled': True, 'case_ids': ['case-test']}], 'retained_documents': []}, <MagicMock id='4585707168'>)
status = 'completed', model = 'stored-model'

    @pytest.mark.parametrize("status,model", [("completed", "stored-model"), ("failed", None)])
    def test_reuse_fragment_survives_pages_and_document_events(monitor, status, model):
        main, _, _, _, _, table = monitor
        row = {**reuse(cached_method="vision", artifact_ids=["opaque-result-1"]), "cached_status": status}
        if model is not None:
            row["cached_model"] = model
        table.query.return_value = {"Items": [dict(row, s3_key="private", text="private", page={"raw": "private"})]}
        response = get(main, limit=1)
        assert response.status_code == 200
        body = response.json()
        assert body["coverage"] == "partial"
>       assert len(body["items"]) == 1
E       assert 0 == 1
E        +  where 0 = len([])

be-intake/tests/test_processing_monitor_cache_reused.py:41: AssertionError
_____ test_reuse_fragment_survives_pages_and_document_events[failed-None] ______

monitor = (<module 'intake_under_test' from '/Users/michal/Projects/wonderfulkb/be-intake/app/main.py'>, <MagicMock id='43914554...type': 'SERVICE', 'enabled': True, 'case_ids': ['case-test']}], 'retained_documents': []}, <MagicMock id='4587662576'>)
status = 'failed', model = None

    @pytest.mark.parametrize("status,model", [("completed", "stored-model"), ("failed", None)])
    def test_reuse_fragment_survives_pages_and_document_events(monitor, status, model):
        main, _, _, _, _, table = monitor
        row = {**reuse(cached_method="vision", artifact_ids=["opaque-result-1"]), "cached_status": status}
        if model is not None:
            row["cached_model"] = model
        table.query.return_value = {"Items": [dict(row, s3_key="private", text="private", page={"raw": "private"})]}
        response = get(main, limit=1)
        assert response.status_code == 200
        body = response.json()
        assert body["coverage"] == "partial"
>       assert len(body["items"]) == 1
E       assert 0 == 1
E        +  where 0 = len([])

be-intake/tests/test_processing_monitor_cache_reused.py:41: AssertionError
___________ test_reuse_and_new_work_keep_distinct_identity_and_scope ___________

monitor = (<module 'intake_under_test' from '/Users/michal/Projects/wonderfulkb/be-intake/app/main.py'>, <MagicMock id='45876635...type': 'SERVICE', 'enabled': True, 'case_ids': ['case-test']}], 'retained_documents': []}, <MagicMock id='4589783424'>)

    def test_reuse_and_new_work_keep_distinct_identity_and_scope(monitor):
        main, resource, *_rest, table = monitor
        rows = [reuse(), {**reuse("reuse-2"), "page_number": 2},
                {**reuse("other-attempt"), "attempt_no": 2},
                {**reuse("other-run"), "run_id": "other-run"},
                event("new-completion", type="PageCompleted", run_id="run-test", attempt_no=1,
                      sequence=8, stage="page_transcription", page_number=1, method="native")]
        table.query.return_value = {"Items": rows}
        response = get(main)
        assert response.status_code == 200
        body = response.json()
        assert set(body) == {"items", "next_token", "observed_at", "coverage"}
>       assert [item["event_id"] for item in body["items"]] == ["reuse-observed", "reuse-2", "new-completion"]
E       AssertionError: assert ['new-completion'] == ['reuse-obser...w-completion']
E         
E         At index 0 diff: 'new-completion' != 'reuse-observed'
E         Right contains 2 more items, first extra item: 'reuse-2'
E         Use -v to get more diff

be-intake/tests/test_processing_monitor_cache_reused.py:69: AssertionError
__ test_reuse_empty_evaluated_window_keeps_position_and_bound_cursor[scope0] ___

monitor = (<module 'intake_under_test' from '/Users/michal/Projects/wonderfulkb/be-intake/app/main.py'>, <MagicMock id='45897844...type': 'SERVICE', 'enabled': True, 'case_ids': ['case-test']}], 'retained_documents': []}, <MagicMock id='4587660560'>)
scope = {'attempt_no': 2}

    @pytest.mark.parametrize("scope", [{"attempt_no": 2}, {"run_id": "other-run"}])
    def test_reuse_empty_evaluated_window_keeps_position_and_bound_cursor(monitor, scope):
        from document_processing.audit.audit_queries import document_key
        main, _, docs, _, policy, table = monitor
        key = {"pk": document_key("case-test", "doc-test"), "sk": "EVENT#other-observation"}
        table.query.side_effect = [{"Items": [{**reuse(), **scope}], "LastEvaluatedKey": key},
                                   {"Items": [reuse()]}]
        first = get(main, limit=1)
        assert first.status_code == 200 and first.json()["items"] == []
        token = first.json()["next_token"]
        assert token and table.query.call_count == 1
        for field, value in [("operation", "steps"), ("operation", "document_events"),
                             ("attempt_no", 2), ("run_id", "other-run"),
                             ("case_id", "other-case"), ("document_id", "other-doc")]:
            data = json.loads(base64.urlsafe_b64decode(token + "=" * (-len(token) % 4)))
            data[field] = value
            altered = base64.urlsafe_b64encode(json.dumps(data).encode()).decode()
            assert get(main, next_token=altered).status_code == 400
        assert table.query.call_count == 1
        second = get(main, limit=1, next_token=token)
        assert second.status_code == 200
>       assert second.json()["items"][0]["event_id"] == "reuse-observed"
               ^^^^^^^^^^^^^^^^^^^^^^^^^
E       IndexError: list index out of range

be-intake/tests/test_processing_monitor_cache_reused.py:99: IndexError
__ test_reuse_empty_evaluated_window_keeps_position_and_bound_cursor[scope1] ___

monitor = (<module 'intake_under_test' from '/Users/michal/Projects/wonderfulkb/be-intake/app/main.py'>, <MagicMock id='45876582...type': 'SERVICE', 'enabled': True, 'case_ids': ['case-test']}], 'retained_documents': []}, <MagicMock id='4585711536'>)
scope = {'run_id': 'other-run'}

    @pytest.mark.parametrize("scope", [{"attempt_no": 2}, {"run_id": "other-run"}])
    def test_reuse_empty_evaluated_window_keeps_position_and_bound_cursor(monitor, scope):
        from document_processing.audit.audit_queries import document_key
        main, _, docs, _, policy, table = monitor
        key = {"pk": document_key("case-test", "doc-test"), "sk": "EVENT#other-observation"}
        table.query.side_effect = [{"Items": [{**reuse(), **scope}], "LastEvaluatedKey": key},
                                   {"Items": [reuse()]}]
        first = get(main, limit=1)
        assert first.status_code == 200 and first.json()["items"] == []
        token = first.json()["next_token"]
        assert token and table.query.call_count == 1
        for field, value in [("operation", "steps"), ("operation", "document_events"),
                             ("attempt_no", 2), ("run_id", "other-run"),
                             ("case_id", "other-case"), ("document_id", "other-doc")]:
            data = json.loads(base64.urlsafe_b64decode(token + "=" * (-len(token) % 4)))
            data[field] = value
            altered = base64.urlsafe_b64encode(json.dumps(data).encode()).decode()
            assert get(main, next_token=altered).status_code == 400
        assert table.query.call_count == 1
        second = get(main, limit=1, next_token=token)
        assert second.status_code == 200
>       assert second.json()["items"][0]["event_id"] == "reuse-observed"
               ^^^^^^^^^^^^^^^^^^^^^^^^^
E       IndexError: list index out of range

be-intake/tests/test_processing_monitor_cache_reused.py:99: IndexError
=============================== warnings summary ===============================
be-intake/tests/test_processing_monitor_cache_reused.py:9
be-intake/tests/test_processing_monitor_cache_reused.py:9
  /Users/michal/Projects/wonderfulkb/be-intake/tests/test_processing_monitor_cache_reused.py:9: DeprecationWarning: jsonschema.RefResolver is deprecated as of v4.18.0, in favor of the https://github.com/python-jsonschema/referencing library, which provides more compliant referencing behavior as well as more flexible APIs for customization. A future release will remove RefResolver. Please file a feature request (on referencing) if you are missing an API for the kind of customization you need.
    from jsonschema import RefResolver

be-document-processing/.venv/lib/python3.13/site-packages/fastapi/testclient.py:1
  /Users/michal/Projects/wonderfulkb/be-document-processing/.venv/lib/python3.13/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
FAILED be-intake/tests/test_processing_monitor_cache_reused.py::test_reuse_fragment_survives_pages_and_document_events[completed-stored-model]
FAILED be-intake/tests/test_processing_monitor_cache_reused.py::test_reuse_fragment_survives_pages_and_document_events[failed-None]
FAILED be-intake/tests/test_processing_monitor_cache_reused.py::test_reuse_and_new_work_keep_distinct_identity_and_scope
FAILED be-intake/tests/test_processing_monitor_cache_reused.py::test_reuse_empty_evaluated_window_keeps_position_and_bound_cursor[scope0]
FAILED be-intake/tests/test_processing_monitor_cache_reused.py::test_reuse_empty_evaluated_window_keeps_position_and_bound_cursor[scope1]
5 failed, 7 passed, 3 warnings in 0.46s
````

### Standard Error
````text

````

## GREEN Phase
- **Timestamp:** 2026-10-20T09:50:34.933039+00:00
- **Test command:** `be-document-processing/.venv/bin/python -m pytest -q be-intake/tests/test_processing_monitor_cache_reused.py`
- **Exit code:** 0

### Standard Output
````text
............                                                             [100%]
=============================== warnings summary ===============================
be-intake/tests/test_processing_monitor_cache_reused.py:9
be-intake/tests/test_processing_monitor_cache_reused.py:9
  /Users/michal/Projects/wonderfulkb/be-intake/tests/test_processing_monitor_cache_reused.py:9: DeprecationWarning: jsonschema.RefResolver is deprecated as of v4.18.0, in favor of the https://github.com/python-jsonschema/referencing library, which provides more compliant referencing behavior as well as more flexible APIs for customization. A future release will remove RefResolver. Please file a feature request (on referencing) if you are missing an API for the kind of customization you need.
    from jsonschema import RefResolver

be-document-processing/.venv/lib/python3.13/site-packages/fastapi/testclient.py:1
  /Users/michal/Projects/wonderfulkb/be-document-processing/.venv/lib/python3.13/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
12 passed, 3 warnings in 0.54s
````

### Standard Error
````text

````
