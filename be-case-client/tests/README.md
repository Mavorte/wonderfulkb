# be-case-client/tests

Offline testy bez sítě a bez AWS.

```bash
python3 -m unittest discover -s be-case-client/tests
```

- `test_case_client_lambda.py`: skutečný handler nad in-memory repository (validace, filtry, stránkování, vytvoření case s generovaným `case_id`).
- `test_case_client_template.py`: statická kontrola SAM šablony `template.yaml`.
