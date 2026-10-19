---
name: "case-evaluation"
description: "Evaluate a loan case before disbursement: start an evaluation run, record each business rule with its tool, and finish with the verdict."
---

# Case Evaluation

The task gives you a `case_id`. You check the case's documents against the business rules and record each rule's result with its own tool. Each result is saved as soon as you record it, and the backoffice app shows it live.

## Steps

1. Call `start_evaluation` with the `case_id`. If it returns an `error`, stop and set the task to failed with that error; there is no run to close. Do not guess data.
2. Find the loan agreement (label `smlouva_o_uveru`, or a title containing "Smlouva") and read it with `get_document`.
3. Record the agreement rules: `loan_agreement_present`, `required_documents_present`, `recipient_matches_client`.
4. Record the eight document contents rules. Read one matched document at a time with `get_document`, record its rule, then move on.
5. Read the documents you haven't read yet, such as the payment agreement and the VOP. After reading each document, write down a short note of the values it shows for the consistency rules (below), with its page.
6. Record the eight consistency rules from your notes.
7. Call `finish_evaluation` with a short summary. It is refused while any rule is unrecorded.
8. Complete the task with the verdict and summary.

If an evaluate tool returns `accepted: false`, read its `problems`, correct the input and call it again. Recording a rule again replaces its earlier result. If a tool keeps failing after `start_evaluation`, call `fail_evaluation` with the reason, then set the task to failed.

Every evaluate tool takes `reasoning`: say in one to three sentences what you looked at and why you chose the status. The KB reviewer reads it.

## Rules

**loan_agreement_present** → `evaluate_loan_agreement_present`
- `passed` with the agreement's `document_id`, or `missing` if there is no loan agreement.
- If it is missing, record `required_documents_present` as `cannot_verify` with no requirements. Record `recipient_matches_client` and every contents rule as `cannot_verify` too. Still record the consistency rules from the other documents.

**required_documents_present** → `evaluate_required_documents`
- The agreement lists the documents the recipient must submit before disbursement ("Příjemce financování je povinen před čerpáním úvěru předložit...", "Před čerpáním musí být doloženo..."). It also names the guarantee and security documents under "Zajištění úvěru".
- List every one of them as a requirement, named by what it is (e.g. "faktura (daňový doklad)"). Never refer to a requirement by a letter or number, in the record or in the summary. Give each the `document_id` of the uploaded document that provides it, matched by label and title, or no `document_id` if nothing matches.
- What a requirement says its document must contain is part of that requirement, not a separate one. For example, "daňový doklad obsahující detailní specifikaci předmětu (včetně výrobního čísla)" is one `invoice` requirement, not an invoice plus a technical specification.
- Give each requirement its `type`: the kind of document it asks for. Use `other` for anything that is none of the eight types, e.g. the supplier's confirmation of the title transfer. One document can provide several requirements.
- Only whether a matching document exists counts here; its contents are checked by later rules.
- Typical matches:

  | Requirement | `type` | Document |
  | --- | --- | --- |
  | tax document / invoice (daňový doklad, faktura) | `invoice` | an invoice; not the agreement itself |
  | purchase agreement or confirmed order (kupní smlouva, objednávka) | `purchase_contract` | `objednavka`, purchase contract |
  | signed handover (předávací protokol, dodací list) | `handover_protocol` | `predavaci_protokol` |
  | payment proof (výpis z účtu, úhrada) | `payment_proof` | bank statement or payment confirmation (`doklad_o_uhrade`); not the payment agreement (dohoda o zaplacení) |
  | guarantee declaration (prohlášení o ručení) | `guarantee` | `ruceni` |
  | security transfer (zajišťovací převod vlastnického práva) | `security_transfer` | `zajistovaci_prevod` |
  | insurance vinculation (vinkulace pojištění) | `insurance_vinculation` | `vinkulace_pojisteni` |
  | technical specification | `technical_specification` | a specification, possibly inside the order PDF |

- The VOP (general terms) and the insurance vinculation count only if the agreement asks for them.
- Status: `passed` if every requirement has a document, otherwise `missing`.

**recipient_matches_client** → `evaluate_recipient_match`
- Give the recipient (příjemce financování) name and IČO exactly as the agreement shows them, with the `document_id` and page.
- `passed` if both match the client record from `start_evaluation`, `conflict` if either differs. A placeholder or malformed IČO (an IČO has 8 digits) is a `conflict`.
- `cannot_verify` only if there is no client record, or the agreement has no readable recipient block.
- The tool compares the values itself and rejects a status that doesn't fit them.

## Document contents rules

Each rule checks the one document that `required_documents_present` matched to its type; record that rule first. The tool's `fields` parameter lists the fields.
- If no document was matched to the type, send no `document_id` or `fields`, and use:
  - `missing` if the agreement requires one but none was uploaded;
  - `cannot_verify` if `required_documents_present` has no requirements (no readable loan agreement);
  - `not_applicable` if the agreement doesn't require one.
- Otherwise read the document and list every field: its value as the document shows it, kept short, with the page. Leave out the value for a field the document doesn't show.
- Only presence counts here, not whether values agree with other documents; the consistency rules check that.
- `missing` if any field or signature is absent, `passed` if everything is there.
- `cannot_verify` only if the document is too hard to read to tell: `pages_failed`, or `confidence` below 0.8. A page with empty text that isn't in `pages_failed` is blank, and what should be on it is `missing`.
- Signatures: `get_document` lists the detected signatures by role (`provider` = SGEF, `borrower`, `supplier`, `guarantor`, `insurer`). The tool counts them itself; SGEF signs with two people. Say in `reasoning` whose signature is missing.

| Rule → tool `evaluate_<rule>` | Document | What to look for |
| --- | --- | --- |
| `invoice_contents` | invoice / tax document | Issuer and customer identity, number, subject, price, VAT, issue and supply dates, due date, payment details. |
| `purchase_contract_contents` | purchase contract / order | Buyer, seller, subject, price. An order counts only when the seller confirms it, by signature or stamp. |
| `handover_protocol_contents` | handover protocol / delivery note | Who hands over and who receives, the asset and serial number, date, condition or quantity, both signatures. Handwritten values appear as "(ručně)". |
| `technical_specification_contents` | technical specification | Product, model or type, manufacturer, parameters, serial number or VIN if there is one. |
| `payment_proof_contents` | bank statement / payment confirmation | Payer and payee accounts, amount, currency, date, and what links it to the invoice or financing. |
| `security_transfer_contents` | security transfer of ownership | SGEF and the recipient, the secured contract number, the asset with serial number and value, the transfer terms, date, signatures. |
| `insurance_vinculation_contents` | insurance vinculation | Policyholder, insurer, SGEF as beneficiary, the asset, policy number, amount, the commitment to pay SGEF, the insurer's date and signature. |
| `guarantee_contents` | guarantee declaration | Guarantor, SGEF as creditor, the recipient as debtor, the secured contract, scope, the guarantor's commitment to pay, date, signatures. |

## Consistency rules

Each rule compares one entity across every document that shows it (the control matrix). Give the value each document shows, exactly as written, with its `document_id` and page. List a document once per page that shows a different value, e.g. a loan number on page 1 and another on page 3. List every attribute, with an empty values list if no document shows it.
- The tool adds the reference values itself: the client record for the recipient, the case record for the asset and the loan number, and SGEF's own data for SGEF. Don't list them.
- It normalizes the values (case, spaces, diacritics, leading zeros, number formats) and compares them. Identifiers and numbers must match exactly. A malformed value, such as an IČO that is not 8 digits or `XXXXXXX`, is a `conflict`.
- Text values that only differ in how they are written (address order, "nám." vs "náměstí", a short vs a full asset name) can be judged the same: list the attribute in `equivalent` and say why in `reasoning`. A different company name, such as Epirock vs Epiroc, is not just spelling; say in `reasoning` how you judged it.
- `passed` if everything agrees, `conflict` if anything differs. `cannot_verify` only if no attribute appears in two sources.
- Leave out a value you can't read reliably (low confidence or garbled), and say so in `reasoning`.
- Count only values that refer to this entity. A stamp of the recipient with another IČO counts; a VOP version number is not a loan number.

| Rule → tool | Attributes | Where to look |
| --- | --- | --- |
| `recipient_consistent` → `evaluate_recipient_consistent` | name, IČO, DIČ, address | Every party block and stamp of the recipient (příjemce financování, kupující, odběratel, úvěrovaný, dlužník). |
| `client_status_valid` → `evaluate_client_status` | — | The tool checks the client record's status and KYC. Give the name of each person who signs for the recipient, with the page. Someone not among the client's authorized signatories is a `conflict`. |
| `supplier_consistent` → `evaluate_supplier_consistent` | name, IČO, DIČ, address, bank account | The supplier (dodavatel, prodávající) in the agreement, order, invoice, handover and payment agreement. |
| `provider_consistent` → `evaluate_provider_consistent` | name, IČO, DIČ, bank account | SGEF (poskytovatel financování, věřitel, oprávněný z pojištění) in every document. |
| `asset_consistent` → `evaluate_asset_consistent` | name, manufacturer, serial number/VIN, year | The financed asset in the agreement, order, handover, security transfer and vinculation. |
| `amounts_consistent` → `evaluate_amounts_consistent` | price without VAT, VAT amount, price with VAT, loan amount | List an amount only where the document states that same quantity; a guarantee's scope or an insured value is not the price. |
| `contract_number_consistent` → `evaluate_contract_number_consistent` | loan contract number | Every reference to the loan contract (smlouva o úvěru č.), e.g. in the security transfer, vinculation, guarantee and payment agreement. |
| `guarantor_consistent` → `evaluate_guarantor_consistent` | name, IČO, address | The guarantor (ručitel) in the agreement's security section and the guarantee. `not_applicable` if the case has no guarantor. |

## Other observations

Other findings you notice don't belong to a rule yet. Examples:
- an uploaded document that no rule checks but that is blank or unreadable, such as an empty payment agreement;
- text that looks inserted, such as an all-caps clause.

Mention them in the `finish_evaluation` summary. Don't change a rule's status because of them.
