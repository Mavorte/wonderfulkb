# Case document statuses

Status of each required document in a case, as evaluated by the review agent. Baseline: the case review mock (`CheckStatus` = `pass | fail | warn`, the missing-documents list and low-confidence OCR values in the activity timeline).

| Value | Czech | Meaning | Review UI icon | Example (case Z25_00024) |
|---|---|---|---|---|
| `pending` | Čeká na zpracování | Not evaluated yet (case is `open`, `intake_in_progress` or `evaluating`) | — | — |
| `fulfilled` | Splněno | Present, readable, signed where required, consistent with other documents and the core system | pass | Handover protocol |
| `missing` | Chybí | Required document is not in the pack | fail | Supplier tax invoice, proof of VAT payment |
| `mismatch` | Nesoulad | Present, but its data contradicts other documents or the core system | fail | Loan contract (wrong supplier IČ), guarantee (wrong loan number) |
| `unverifiable` | Nelze ověřit | Present, but the agent cannot confirm it: unreadable or low-confidence OCR, blank field, external source unavailable | warn | Handwritten serial number, blank signatory function |

## Derivation

A document takes the worst status among its findings, in this order:

`missing` > `mismatch` > `unverifiable` > `fulfilled`

The case checklist ("7 of 9") counts `fulfilled` documents.

## Design notes

- **No "needs review" document status.** The mock's `warn` mixes "cannot tell" and "looks off". At document level these are `unverifiable` and `mismatch`; the human judgement call happens at case level (`awaiting_decision`, see [case-statuses.md](case-statuses.md)).
- **Severity stays on findings.** `blocking` / `material` / `minor` describes how serious a finding is, not the document's state. A `mismatch` document can carry a blocking or a minor finding.

## Open questions

- Unsigned or expired documents: fold into `mismatch`, or add `invalid` (Neplatné)?
