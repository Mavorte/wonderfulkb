# Case Evaluator

Backoffice agent that checks a loan case's documents before disbursement. A webhook or a manual task gives it a `case_id`. The agent loads the case and reads the documents it needs. It records each business rule's result as it goes, into tables the backoffice app can poll. At the end it gives a verdict: `ready`, `needs_correction` or `needs_review`.

The build follows the phases in `kb-hackathon/evaluation_agent_plan.md`. This is **phase 3**: the phase 1 rules, a contents rule per document type (phase 2), and a consistency rule per entity (phase 3). Each rule is recorded by its own tool.

## How it works

The tools call the Functions in the `agent-functions` app (`repos/agent-functions/`) through `context.functions.run("agent-functions/<slug>")`. The Functions hold the API keys and the live/mock switch. The tools also write the evaluation tables directly through `ctx.tables`.

| Tool | What it does |
| --- | --- |
| `start_evaluation(case_id)` | Loads the case, client and document list through `eval-case-get` and `eval-documents-list`. Inserts a `running` row in `case_evaluations`, and keeps the run in KV: evaluation ID, client, the case's loan number, asset and serial number, and documents. |
| `get_document(document_id)` | One document's text, split into pages, from `eval-document-get`, and its signatures from `eval-document-signatures`. It keeps what it saw in KV: page count, empty pages, `pages_failed`, confidence and signature roles. |
| `evaluate_loan_agreement_present` | Records that rule. |
| `evaluate_required_documents` | Records that rule. It also keeps the typed requirement → document mapping in KV for the contents rules. |
| `evaluate_recipient_match` | Records that rule. |
| `evaluate_<type>_contents` (8 tools) | Each records one document contents rule (see below). |
| `evaluate_<entity>_consistent` (7 tools), `evaluate_client_status` | Each records one consistency rule (see below). |
| `finish_evaluation(summary)` | Refused while any rule is unrecorded. Then computes the verdict, sets the case status to `awaiting_decision` through `agent-functions/case-status-set` (if that fails the run stays open and the call is refused), and marks the run `completed`. |
| `fail_evaluation(reason)` | Marks the run `failed` when it can't be finished. |

The `evaluate_*` tools take typed inputs plus a required `reasoning`. The tool checks the chosen status against the inputs and the run; for example, it rejects `passed` when the IČO differs. A rejected call writes nothing and returns `{accepted: false, problems}`. An accepted call upserts one row in `case_evaluation_results`. Recording a rule again replaces its row.

Code layout:

| Path | Contents |
| --- | --- |
| `lib/rules.ts` | Rule registry and verdict. |
| `lib/run.ts` | Run state and table writes. |
| `lib/rules/*.ts` | Per-rule validators. The eight contents rules share one validator, `contents.ts`, with one spec each in `contentSpecs.ts`. |
| `lib/record.ts` | Shared record flow. |
| `lib/rules/consistency.ts`, `consistencySpecs.ts` | Validator shared by the `*_consistent` rules, and one spec per entity. |
| `lib/rules/clientStatus.ts` | Validator of `client_status_valid`. |
| `lib/tools.test.ts` | Checks that each contents and consistency tool lists its spec's fields or attributes. |
| `tools/*/index.ts` | One tool each, with its params and handler written out in full. |
| `skills/case-evaluation/SKILL.md` | The agent's instructions. |

To add a rule:
1. Add an entry to `RULES`.
2. Add a validator in `lib/rules/`. For a new document type, add a spec to `contentSpecs.ts` and a type to `DOCUMENT_TYPES` instead. For a new entity to compare, add a spec to `consistencySpecs.ts`.
3. Add a `tools/evaluate_<rule>/` tool. For a contents or consistency rule, copy a tool of the same kind and list the spec's field or attribute keys in its params; `lib/tools.test.ts` checks they match.
4. Register the tool in `config.json` `global_tools`.
5. Add a paragraph to `SKILL.md`.

## Data

The tables are declared in `repos/agent-functions/tables/`, which documents their columns. The backoffice app has them linked.

- `agent_functions.case_evaluations`: one row per run.
- `agent_functions.case_evaluation_results`: one row per rule per run.

`start_evaluation` writes a `pending` result row for every rule, with an empty `reasoning` and no `recorded_at`, so the checklist is known from the start. Recording a rule replaces its row. Each row has the rule's `category`, the backoffice checklist group it is shown under (`RULE_CATEGORIES` in `lib/rules.ts`): `completeness`, `consistency`, `client_status` or `supplier`.

To follow a case, read the latest `case_evaluations` row for its `case_id` (by `started_at`), then its `case_evaluation_results` rows. Progress is the number of rows whose status is not `pending`, out of `rules_total`; per group, the same count within a `category`. A failed run keeps the rows it never recorded as `pending`.

## Phase 1 rules

| Rule | Check |
| --- | --- |
| `loan_agreement_present` | A loan agreement is among the documents. |
| `required_documents_present` | Every document the agreement requires before disbursement (its list of documents to submit, plus the security documents) has a matching upload. |
| `recipient_matches_client` | The recipient's name and IČO in the agreement match the client record. |

`required_documents_present` gives each requirement a `type`: `invoice`, `purchase_contract`, `handover_protocol`, `technical_specification`, `payment_proof`, `security_transfer`, `insurance_vinculation`, `guarantee` or `other`.

## Phase 2 rules: document contents

One rule per document type in `business_rules.docx`. Each checks the document that `required_documents_present` matched to its type.

| Rule | Fields | Signatures |
| --- | --- | --- |
| `invoice_contents` | Issuer, customer, number, subject, price, VAT, issue date, supply date (optional), due date, payment details (optional) | — |
| `purchase_contract_contents` | Buyer, seller, subject, price | buyer, seller |
| `handover_protocol_contents` | Who hands over, who receives, asset, date, condition or quantity | supplier, recipient |
| `technical_specification_contents` | Product, model, manufacturer, parameters, serial number (optional) | — |
| `payment_proof_contents` | Payer and payee accounts, amount, currency, date, link to the invoice or financing | — |
| `security_transfer_contents` | SGEF, recipient, secured contract, asset, serial number, value, transfer terms, date | SGEF ×2, recipient |
| `insurance_vinculation_contents` | Policyholder, insurer, SGEF as beneficiary, asset, policy number, amount, benefit clause, insurer's date | insurer |
| `guarantee_contents` | Guarantor, SGEF, recipient as debtor, secured contract, scope, commitment, date | guarantor, SGEF ×2 |

The agent lists every field with the value it read and the page. The tool then checks:
- that `required_documents_present` is recorded, and that the document is the one it matched;
- that the document was read with `get_document`;
- that every field is listed, and that no value comes from a page without text.

The tool counts the signatures per role itself, from the signatures `get_document` loaded. Signatures are checked for presence only.

Statuses:
- `passed`: everything is there.
- `missing`: a field or signature is absent; a blank page counts as absent. Also used when the agreement requires the document but none was uploaded (found "Required, but not uploaded").
- `cannot_verify`: only for a hard-to-read document: `pages_failed`, confidence below 0.8, or signatures that could not be loaded. Also used when `required_documents_present` has no requirements (no readable loan agreement), so it is unknown whether the document is needed.
- `not_applicable`: the agreement doesn't require this type of document.

When no document was matched, the tool works out the status from `required_documents_present` and rejects any other.

## Phase 3 rules: consistency across documents

One rule per entity of the control matrix (`Hack_Seznam kontrol.xlsx`). The agent gives the value each document shows, as `{document_id, page, value}` per attribute. The tool adds the reference values itself, then normalizes and compares.

| Rule | Attributes | Reference |
| --- | --- | --- |
| `recipient_consistent` | name, IČO, DIČ, address | client record |
| `client_status_valid` | client `status` and `kyc.status`, and the people signing for the recipient | client record (`status=active`, `kyc.status=ok`, `signatories[].authorized`) |
| `supplier_consistent` | name, IČO, DIČ, address, bank account | — |
| `provider_consistent` | provider's name, IČO, DIČ, bank account | — |
| `asset_consistent` | name, manufacturer, serial number/VIN, year | case record (`metadata.asset`, `metadata.serial_number`) |
| `amounts_consistent` | price without VAT, VAT, price with VAT, loan amount | — |
| `contract_number_consistent` | loan contract number | case record (`metadata.loan_number`) |
| `guarantor_consistent` | name, IČO, address; `not_applicable` without a guarantor | — |

`provider_consistent` is not in the plan's table. It was added because the unhappy case's provider name, account and DIČ are wrong, and no other entity covers the provider. It only compares the documents with each other, since the synthetic cases use another provider (Nerovex Finance s.r.o.) than SGEF.

The agent lists each distinct value once, with every place it appears as `<ref>:<page>`, e.g. `{"value": "Epiroc Czech Republic s.r.o.", "at": ["D1:1", "D3:2"]}`. Documents go by the short refs `start_evaluation` gives them (D1, D2, …), which every tool accepts in place of a `document_id`. Writing each value once with short refs, instead of one entry per document with its full ID, roughly halves the output of the turn that records these eight rules, the slowest turn of a run.

The tool checks:
- that each value comes from a case document read with `get_document`, from a page with text;
- that every attribute is listed, possibly with no values.

Normalization ignores case, spaces, diacritics and punctuation in text, leading zeros in account numbers, and Czech/English number formats in amounts. IČO must be 8 digits and DIČ `CZ` plus 8–10 digits; any other value is a `conflict`.

Text attributes the agent judges to be the same thing written differently (address order, a short vs a full asset name) go in `equivalent`, with the reason in `reasoning`. Identifiers and amounts can't be listed there.

Statuses:
- `passed`: every value agrees.
- `conflict`: a value differs or is malformed.
- `cannot_verify`: only if no attribute appears in two sources.
- `not_applicable`: only for `guarantor_consistent`.

`client_status_valid` compares signatory names ignoring case, diacritics, academic titles and name order.

## Regions behind each finding

`get_document` also loads the document's regions from `agent-functions/eval-document-regions`: labelled paragraphs and table rows of text-layer pages, with their position (AWS documents API). The agent doesn't see them. When a rule is recorded, `lib/regions.ts` places each source on the region, and the line within it, that shows the cited value. It prefers regions whose label and party fit the rule, e.g. the supplier's `smluvni_strana` block. Each `sources` entry can then carry:

| Field | Meaning |
| --- | --- |
| `region_id`, `page` | e.g. `p1-r04` on page 1. |
| `bbox` | `[x0, y0, x1, y1]`, 0–1 of the page, origin top left; narrowed to the value's lines when it sits in some of them. |
| `quote` | The document's own text at that place. |
| `role` | `evidence`; `compare_a`, `compare_b`, … for the sides of a conflict (`a` is the reference value's side); `declaration` for the agreement clause requiring a missing document; `missing_value` for where a missing signature or party should be. |
| `field` | The field or attribute whose value is there, as the rule's tool names it: a `*_contents` field (`creditor`, `asset_value`, …), a consistency attribute (`ico`, `bank_account`, …), `agreement_name` / `agreement_ico`, or `signatory`. |
| `issue` | The issue this place shows: the attribute (`IČO`), the requirement, `<party> signature`, `unauthorized signatory`. |
| `anchor` | `region`, `lines`, or `page_only` when no region was found. |

Per issue:
- **Consistency conflict:** every value of the differing attribute, by side.
- **Missing required document:** the agreement's `povinny_podklad` region whose `refers_to` names the document type.
- **Missing signature:** the document's `podpisovy_blok` region for that party.
- **Missing party field:** the party's `smluvni_strana` block.
- **`recipient_matches_client`:** the agreement's name and IČO.
- **`client_status_valid`:** each signatory's name.

Scanned pages have no regions, and the fixture cases have none, so their sources stay at page level (`anchor: page_only`). The field names follow the evidence contract in wonderfulkb `be-validator-agent/docs/regiony-dokumentu-navrh.md`.

## Statuses and verdict

The statuses are `passed`, `missing`, `conflict`, `cannot_verify` and `not_applicable`. The verdict is:
- `needs_correction` if any rule is `missing` or `conflict`;
- otherwise `needs_review` if any is `cannot_verify`;
- otherwise `ready`; `not_applicable` counts like `passed`.

## Triggers

Webhook trigger `case_evaluation`:
- URL: `https://api.sb.wonderful.ai/api/v1/tasks/webhook/6fa39b1e-cfdf-43d3-aedd-f81ee8fcb5de`
- Authentication: the trigger secret goes in the `X-Webhook-Secret` header. It is shown only when the trigger is created; `wful agents triggers list` does not return it.
- A second `case_evaluation` trigger, `062b5032-a738-48c9-810e-b726788add38`, is used by the Case Explorer app (`repos/case-explorer/`). Its secret is stored as `case_eval_webhook_secret`.
- Body: wrap the case ID in `payload`, as `{"payload": {"case_id": "<id>"}}`. Other top-level fields, such as a bare `case_id`, are dropped, and the task ends up waiting for a case ID.

```sh
wful tasks webhook --trigger-id 6fa39b1e-cfdf-43d3-aedd-f81ee8fcb5de --secret <secret> \
  --payload '{"payload": {"case_id": "mock-solom-rec"}}'
```

## Test data

Phase 3 findings on the fixtures: Solom Rec's supplier (Epirock 06493399 vs Epiroc 06493394), its loan number 17023644/25 in the payment agreement and guarantee, and Petr Fiala signing for the recipient. Stavby Fišer's loan number (17171/25 and 171171/25 vs 17026014/25). Unhappy's SGEF name, DIČ and account.

Use the fixture case IDs `mock-solom-rec`, `mock-unhappy` and `mock-stavby-fiser` (see the `agent-functions` README), or a synthetic `mock-eval-*` case (see Evals). They are always served from fixtures, even when the AWS APIs are live.

## Run and test

```sh
pnpm install
pnpm test                                # unit tests: rule validators, run state, table writes, eval answer keys
wful validate && git push && wful validate --remote

# One task, end to end:
wful run backoffice-agent --agent ab87758e-9e78-42b9-8318-ac055c73fe59 \
  --task-type case_evaluation --message '{"case_id":"mock-unhappy"}' --timeout 9m

# Eval batch against the pushed commit:
wful eval run ci_pull_request --batch --snapshot-id "$(wful agents snapshot)" --timeout 900
```

## Evals

Each scenario is a `backoffice_eval` task with a case ID in `task_input`. It runs the real tools against fixture data from `agent-functions`, and passes when:
- the task ends with the expected status;
- `table_assertions` hold: the run's `case_evaluations` row (status and verdict) and the status of each rule in `case_evaluation_results`;
- an LLM judge finds the `expected_behavior` in the tool trace and summary.

Evals run against in-memory copies of the two tables, set up by `table_fixtures` in each scenario, so they never write the real tables. Each fixture holds one seed row, because a copy only knows the columns of its fixture rows.

There are two kinds of scenario:
- **Real cases.** `solom_rec_baseline`, `stavby_fiser_baseline`, `unhappy_recipient_ico` and `unknown_case` are written by hand. The real bundles are messy, so they assert only the statuses that are clear.
- **Synthetic cases.** All the others are generated from `eval-cases/cases.ts`. A clean case (`mock-eval-clean`) is ready for disbursement: every required document is uploaded, complete and signed. Each variant takes something away, so it carries exactly the defects its scenario tests. Each case has a full answer key: every rule's status and the verdict.

| Area | What the synthetic cases cover |
| --- | --- |
| Baseline | The clean case (`ready`) and one with four chained defects. |
| Agreement rules | No agreement; a missing invoice or missing security documents; a recipient IČO typo, a different name, harmless formatting differences and no client record; decoys (a price quote, a payment agreement); one PDF that provides two documents. |
| Contents rules | A missing field or signature for each document type; a blank page (`missing`), a failed page or a poor scan (`cannot_verify`); signatures that can't be loaded; a technical specification that is required. |
| Robustness | The case ID inside a Czech sentence, or no case ID; an instruction to the checker inside a document; an invoice for a different machine; the documents API down; a document that can't be read. |

`eval-cases/cases.test.ts` checks every answer key against the rule validators: what a careful reader finds in the case's documents must be accepted with the expected status, and rejected with any other. A case lists the statuses a tool also accepts as `tool_also_accepts`; those are the judgment calls the skill settles, such as `cannot_verify` instead of `missing` for an unreadable page.

To add or change a synthetic case:
1. Edit `eval-cases/cases.ts`, and `eval-cases/documents.ts` for a new kind of document or defect.
2. Run `pnpm test`.
3. Run `pnpm eval-cases ../agent-functions`. It writes the fixtures to `agent-functions` (`functions/shared/fixtures/eval-cases.json`), and the scenarios and batches here. `--check` only reports files that are out of date.
4. Deploy `agent-functions` (merge to its `main`) before running the evals; the scenarios need its fixtures.

Every scenario of a batch runs at once, so a batch takes about as long as its slowest scenario (6–10 minutes).

| Batch | Scenarios |
| --- | --- |
| `case_evaluation` | All of them. |
| `ci_pull_request` | One scenario per outcome: the clean case (`ready`), chained defects (`needs_correction`), signatures that can't be loaded (`needs_review`), the documents API down (failed run), and the unhappy bundle. |
| `case_evaluation_real_cases` | The four real-case scenarios. |
| `case_evaluation_agreement_rules` | Baseline and agreement rules. |
| `case_evaluation_contents_rules` | Baseline and contents rules. |
| `case_evaluation_robustness` | Robustness, and the unknown case. |

Every pull request runs `ci_pull_request` through the Actions workflow `.wonderful/actions/workflows/ci_pull_request.yml`; `main`'s merge policy requires it to pass. Run it by hand with `wful actions run --workflow .wonderful/actions/workflows/ci_pull_request.yml --watch --exit-status`.
