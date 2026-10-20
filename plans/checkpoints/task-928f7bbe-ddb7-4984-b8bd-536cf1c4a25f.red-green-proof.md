# TDD Red-Green Proof: task-928f7bbe-ddb7-4984-b8bd-536cf1c4a25f

<!-- proof-capture-metadata: {"version":1,"task_id":"task-928f7bbe-ddb7-4984-b8bd-536cf1c4a25f","command":["../../be-document-processing/.venv/bin/python","-m","pytest","-q","tests/test_template.py"],"command_sha256":"88ecd9b38e08a530d36be308487110a56af5df1dbbbd2a259c79849af2a222cb"} -->

## RED Phase
- **Timestamp:** 2026-10-20T08:11:52.328659+00:00
- **Test command:** `../../be-document-processing/.venv/bin/python -m pytest -q tests/test_template.py`
- **Exit code:** 1

### Standard Output
````text
..........Fs                                                             [100%]
=================================== FAILURES ===================================
____________ test_deploy_rollback_template_path_is_script_relative _____________

    def test_deploy_rollback_template_path_is_script_relative():
        script = HERE / "deploy.sh"
        assignments = [
            line for line in script.read_text().splitlines()
            if line.startswith(("SCRIPT_DIR=", "ORIGINAL_TEMPLATE="))
        ]
        result = subprocess.run(
            ["bash", "-c", "\n".join(assignments) + '\nprintf "%s" "$ORIGINAL_TEMPLATE"'],
            cwd=HERE.parent, capture_output=True, text=True, check=True,
        )
>       assert Path(result.stdout) == HERE.parents[1] / "be-intake/documents-table/template.yaml"
E       assert PosixPath('/template.yaml') == (PosixPath('/Users/michal/Projects/wonderfulkb') / 'be-intake/documents-table/template.yaml')
E        +  where PosixPath('/template.yaml') = Path('/template.yaml')
E        +    where '/template.yaml' = CompletedProcess(args=['bash', '-c', 'ORIGINAL_TEMPLATE="$(cd ../../be-intake/documents-table && pwd)/template.yaml"\n...de=0, stdout='/template.yaml', stderr='bash: line 0: cd: ../../be-intake/documents-table: No such file or directory\n').stdout

tests/test_template.py:137: AssertionError
=========================== short test summary info ============================
FAILED tests/test_template.py::test_deploy_rollback_template_path_is_script_relative
````

### Standard Error
````text

````

## GREEN Phase
- **Timestamp:** 2026-10-20T08:12:17.204074+00:00
- **Test command:** `../../be-document-processing/.venv/bin/python -m pytest -q tests/test_template.py`
- **Exit code:** 0

### Standard Output
````text
...........s                                                             [100%]
````

### Standard Error
````text

````
