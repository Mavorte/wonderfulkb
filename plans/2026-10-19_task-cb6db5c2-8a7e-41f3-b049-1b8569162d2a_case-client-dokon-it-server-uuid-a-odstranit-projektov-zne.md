# Plan 2026-10-19: Case Client distinct UUID collision retries

Repair bounded collision allocation in both repositories and add regression coverage for repeated UUID generator output. Preserve all completed parent-task work and limit this follow-up to the unmet acceptance finding.

## Analysis

- `DynamoDBCaseClientRepository.create_case` and `MockCaseClientRepository.create_case` each count three UUID draws, even if multiple draws return the same occupied ID.
- DynamoDB collision tests already use Stubber and deterministic `uuid4` patching in `be-case-client/tests/test_case_client_dynamodb_repository.py`; the mock adapter is exercised in `test_case_client_lambda.py`.
- The original plan and `learnings/architecture/2026-10-19_case-client-server-generated-uuid-collision-contract.md` require collision recovery to use fresh distinct keys, retain bounded fail-closed behavior, and never expose or overwrite occupants.

## Approach

- Track IDs already generated during each create operation; skip duplicate candidates without attempting another insert or counting them toward the three distinct collision candidates.
- Keep allocation finite even if a broken/injected UUID generator repeats forever: bound total UUID draws (three candidate slots, with a small fixed duplicate-draw allowance) and raise the existing sanitized allocation error when that bound or three distinct occupied candidates is exhausted.
- Keep DynamoDB's existing conditional transaction/reason-code classification and strong readback unchanged; only distinct occupied keys may trigger a new candidate attempt.
- Do not touch API behavior, docs, ignore rules, unrelated acceptance artifacts, or previously completed source changes.

## Implementation

1. Add deterministic mock-repository regression coverage: seed/occupy candidate A, have `uuid4` return A twice then free candidate B, and assert creation succeeds at B without changing A; add an always-duplicate sequence case to assert bounded fail-closed exhaustion.
2. Add DynamoDB Stubber regression coverage: script candidate A twice followed by B; expect only one transaction and strong collision read for A, followed by the transaction for B, and assert the returned ID is B and Stubber has no pending responses.
3. Add DynamoDB duplicate-only exhaustion coverage and verify the repository raises without issuing duplicate transaction/read sequences; preserve existing three-distinct-collision exhaustion test.
4. Implement the same distinct-candidate and finite-draw policy in both adapters, retaining lock scope and existing error semantics.

## Testing

- Focused tests: `PYTHONPATH=be-case-client/src AWS_EC2_METADATA_DISABLED=true AWS_ACCESS_KEY_ID=offline AWS_SECRET_ACCESS_KEY=offline python3 -m unittest discover -s be-case-client/tests -p 'test_case_client_lambda.py' -v` and the equivalent command with `test_case_client_dynamodb_repository.py`.
- Full Case Client suite: `PYTHONPATH=be-case-client/src AWS_EC2_METADATA_DISABLED=true AWS_ACCESS_KEY_ID=offline AWS_SECRET_ACCESS_KEY=offline python3 -m unittest discover -s be-case-client/tests -p 'test_*.py' -v`.
- Run registered project verification: `npm --prefix apps/backoffice test && npm --prefix apps/backoffice run build`; record any environment failure accurately.
- Confirm changed files are limited to the two adapters and their corresponding tests; leave unrelated user and acceptance-run artifacts untouched.

## TDD

Follow `skill:tdd` for the fresh GREEN evidence. Do not fabricate a new RED after the parent implementation; link the genuine historical RED from the parent proof if applicable, then capture fresh focused verification for this task.

**Targeted test file:** `be-case-client/tests/test_case_client_dynamodb_repository.py` (DynamoDB) and `be-case-client/tests/test_case_client_lambda.py` (mock).
**Framework:** `unittest`.
**Run commands:** the two focused commands in Testing above.

```python
from unittest.mock import patch

def test_collision_retry_uses_next_distinct_uuid(self):
    # RED before implementation: repeated occupied UUID consumes retry slots.
    with patch('case_client_dynamodb_repository.uuid4',
               side_effect=[occupied_id, occupied_id, available_id]):
        result = self.create(generated_ids=[occupied_id, occupied_id, available_id])
    self.assertEqual(result['case_id'], available_id)
```

| Regression | Expected failure before fix | Expected pass after fix |
|---|---|---|
| Mock: occupied candidate repeats before a free UUID | Allocation fails before reaching free UUID | Creates at the free distinct UUID and preserves occupant |
| DynamoDB: occupied candidate repeats before a free UUID | Exhausts attempt count before second distinct transaction | One collision read for the occupied UUID, then succeeds at free UUID |
| Either adapter: generator repeats indefinitely | Potential unbounded candidate generation if duplicate skipping is naive | Finite, fail-closed allocation with no overwrite or leaked occupant |

## Files

| File | Planned change |
|---|---|
| `be-case-client/src/case_client_dynamodb_repository.py` | Track distinct generated candidates and apply a finite duplicate-draw bound during create collision retries. |
| `be-case-client/src/case_client_mock_repository.py` | Apply the same distinct candidate and finite-draw policy under the existing lock. |
| `be-case-client/tests/test_case_client_dynamodb_repository.py` | Cover repeated UUID output, distinct retry success, bounded duplicate exhaustion, and exact SDK sequence. |
| `be-case-client/tests/test_case_client_lambda.py` | Cover mock repeated candidate output, preservation of occupied case, and bounded exhaustion. |

## Progress

- [x] Read the prior plan, relevant adapters, tests, and collision contract learning.
- [x] Define scoped implementation and regression verification.
- [ ] Implement and verify the acceptance repair in the implementation task.
