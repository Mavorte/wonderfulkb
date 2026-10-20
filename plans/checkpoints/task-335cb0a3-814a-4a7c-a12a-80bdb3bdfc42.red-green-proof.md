# TDD Red-Green Proof: task-335cb0a3-814a-4a7c-a12a-80bdb3bdfc42

<!-- proof-capture-metadata: {"version":1,"task_id":"task-335cb0a3-814a-4a7c-a12a-80bdb3bdfc42","command":["python3","-m","pytest","be-intake/tests/test_processing_monitor_page_routes.py"],"command_sha256":"9128b5bc13e70dd18cce523b05c78253c7d0bb6c43ece80d5148fc01d92274c8"} -->

## RED Phase
- **Timestamp:** 2026-10-20T06:59:35.148264+00:00
- **Test command:** `python3 -m pytest be-intake/tests/test_processing_monitor_page_routes.py`
- **Exit code:** 1

### Standard Output
````text
============================= test session starts ==============================
platform darwin -- Python 3.9.6, pytest-8.4.2, pluggy-1.6.0
rootdir: /Users/michal/Projects/wonderfulkb
plugins: anyio-4.12.1, mock-3.15.1, env-1.1.5, cov-7.0.0
collected 1 item

be-intake/tests/test_processing_monitor_page_routes.py E                 [100%]

==================================== ERRORS ====================================
______ ERROR at setup of test_pages_endpoint_returns_partial_observations ______
file /Users/michal/Projects/wonderfulkb/be-intake/tests/test_processing_monitor_page_routes.py, line 4
  def test_pages_endpoint_returns_partial_observations(intake):
E       fixture 'intake' not found
>       available fixtures: anyio_backend, anyio_backend_name, anyio_backend_options, cache, capfd, capfdbinary, caplog, capsys, capsysbinary, capteesys, class_mocker, cov, doctest_namespace, free_tcp_port, free_tcp_port_factory, free_udp_port, free_udp_port_factory, mocker, module_mocker, monkeypatch, no_cover, package_mocker, pytestconfig, record_property, record_testsuite_property, record_xml_attribute, recwarn, session_mocker, tmp_path, tmp_path_factory, tmpdir, tmpdir_factory
>       use 'pytest --fixtures [testpath]' for help on them.

/Users/michal/Projects/wonderfulkb/be-intake/tests/test_processing_monitor_page_routes.py:4
=========================== short test summary info ============================
ERROR be-intake/tests/test_processing_monitor_page_routes.py::test_pages_endpoint_returns_partial_observations
=============================== 1 error in 0.25s ===============================
````

### Standard Error
````text

````
