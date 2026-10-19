# TDD Red-Green Proof: task-beca6825-147b-43d9-9fb6-694368e70948

<!-- proof-capture-metadata: {"version":1,"task_id":"task-beca6825-147b-43d9-9fb6-694368e70948","command":["/Users/michal/.openclaw/tmp/opencode/case-client-venv/bin/python","-m","unittest","discover","-s","be-case-client/tests","-p","test_case_client_live_tools.py","-v"],"command_sha256":"a3bb48f400caf27850120137dd864b520870537d5626cc60af9b9bfeeda6cd84"} -->

## RED Phase
- **Timestamp:** 2026-10-19T15:24:31.617295+00:00
- **Test command:** `/Users/michal/.openclaw/tmp/opencode/case-client-venv/bin/python -m unittest discover -s be-case-client/tests -p test_case_client_live_tools.py -v`
- **Exit code:** 1

### Standard Output
````text

````

### Standard Error
````text
test_changed_revision_rejected (test_case_client_live_tools.LiveToolGuards.test_changed_revision_rejected) ... FAIL
test_no_redirect_request (test_case_client_live_tools.LiveToolGuards.test_no_redirect_request) ... FAIL
test_secret_exception_redacted (test_case_client_live_tools.LiveToolGuards.test_secret_exception_redacted) ... FAIL
test_write_requires_run_id (test_case_client_live_tools.LiveToolGuards.test_write_requires_run_id) ... FAIL
test_wrong_account_rejected (test_case_client_live_tools.LiveToolGuards.test_wrong_account_rejected) ... FAIL

======================================================================
FAIL: test_changed_revision_rejected (test_case_client_live_tools.LiveToolGuards.test_changed_revision_rejected)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/michal/Projects/wonderfulkb/be-case-client/tests/test_case_client_live_tools.py", line 30, in test_changed_revision_rejected
    with self.assertRaises(ValueError):
         ~~~~~~~~~~~~~~~~~^^^^^^^^^^^^
AssertionError: ValueError not raised

======================================================================
FAIL: test_no_redirect_request (test_case_client_live_tools.LiveToolGuards.test_no_redirect_request)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/michal/Projects/wonderfulkb/be-case-client/tests/test_case_client_live_tools.py", line 38, in test_no_redirect_request
    self.assertIsNone(NoRedirect().redirect_request(
    ~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
        None, None, 302, 'Found', {}, 'https://example.invalid/'))
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError: <urllib.request.Request object at 0x105020050> is not None

======================================================================
FAIL: test_secret_exception_redacted (test_case_client_live_tools.LiveToolGuards.test_secret_exception_redacted)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/michal/Projects/wonderfulkb/be-case-client/tests/test_case_client_live_tools.py", line 34, in test_secret_exception_redacted
    self.assertNotIn('fake-key-for-offline-test',
    ~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
        safe_error(RuntimeError('fake-key-for-offline-test')))
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError: 'fake-key-for-offline-test' unexpectedly found in 'fake-key-for-offline-test'

======================================================================
FAIL: test_write_requires_run_id (test_case_client_live_tools.LiveToolGuards.test_write_requires_run_id)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/michal/Projects/wonderfulkb/be-case-client/tests/test_case_client_live_tools.py", line 26, in test_write_requires_run_id
    with self.assertRaises(ValueError):
         ~~~~~~~~~~~~~~~~~^^^^^^^^^^^^
AssertionError: ValueError not raised

======================================================================
FAIL: test_wrong_account_rejected (test_case_client_live_tools.LiveToolGuards.test_wrong_account_rejected)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/michal/Projects/wonderfulkb/be-case-client/tests/test_case_client_live_tools.py", line 21, in test_wrong_account_rejected
    with self.assertRaises(ValueError):
         ~~~~~~~~~~~~~~~~~^^^^^^^^^^^^
AssertionError: ValueError not raised

----------------------------------------------------------------------
Ran 5 tests in 0.002s

FAILED (failures=5)
````

## GREEN Phase
- **Timestamp:** 2026-10-19T15:29:41.486201+00:00
- **Test command:** `/Users/michal/.openclaw/tmp/opencode/case-client-venv/bin/python -m unittest discover -s be-case-client/tests -p test_case_client_live_tools.py -v`
- **Exit code:** 0

### Standard Output
````text

````

### Standard Error
````text
test_all_target_dimensions_and_url_fail_closed (test_case_client_live_tools.LiveToolGuards.test_all_target_dimensions_and_url_fail_closed) ... ok
test_backup_hash_and_private_permissions (test_case_client_live_tools.LiveToolGuards.test_backup_hash_and_private_permissions) ... ok
test_changed_revision_rejected (test_case_client_live_tools.LiveToolGuards.test_changed_revision_rejected) ... ok
test_concurrent_revision_prevents_deploy_or_rollback (test_case_client_live_tools.LiveToolGuards.test_concurrent_revision_prevents_deploy_or_rollback) ... ok
test_default_write_denied_and_run_id_validated (test_case_client_live_tools.LiveToolGuards.test_default_write_denied_and_run_id_validated) ... ok
test_no_redirect_request (test_case_client_live_tools.LiveToolGuards.test_no_redirect_request) ... ok
test_post_transport_never_retries_and_rate_is_shared (test_case_client_live_tools.LiveToolGuards.test_post_transport_never_retries_and_rate_is_shared) ... ok
test_read_only_default_does_not_seed_or_post (test_case_client_live_tools.LiveToolGuards.test_read_only_default_does_not_seed_or_post) ... ok
test_sdk_exception_redaction_in_stdout_and_manifest (test_case_client_live_tools.LiveToolGuards.test_sdk_exception_redaction_in_stdout_and_manifest) ... ok
test_secret_exception_redacted (test_case_client_live_tools.LiveToolGuards.test_secret_exception_redacted) ... ok
test_task_wide_budgets_and_deadline (test_case_client_live_tools.LiveToolGuards.test_task_wide_budgets_and_deadline) ... ok
test_update_revision_waiters_and_original_environment_restore (test_case_client_live_tools.LiveToolGuards.test_update_revision_waiters_and_original_environment_restore) ... ok
test_write_requires_run_id (test_case_client_live_tools.LiveToolGuards.test_write_requires_run_id) ... ok
test_wrong_account_rejected (test_case_client_live_tools.LiveToolGuards.test_wrong_account_rejected) ... ok

----------------------------------------------------------------------
Ran 14 tests in 0.006s

OK
````
