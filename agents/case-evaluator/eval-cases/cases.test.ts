// Checks each eval case's answer key against the rule validators: the reading a
// careful agent makes of the case's documents must be accepted with the expected
// status, and rejected with any other (except the judgment calls a case lists in
// tool_also_accepts). So a scenario never expects a status the tools refuse.

import { describe, expect, it } from "vitest";
import { RULE_IDS, type RuleId, type Status, getVerdict } from "../lib/rules";
import type { CheckOutcome } from "../lib/rules/check";
import { GUARANTEE, HANDOVER_PROTOCOL, INSURANCE_VINCULATION, INVOICE, PAYMENT_PROOF, PURCHASE_CONTRACT, SECURITY_TRANSFER, TECHNICAL_SPECIFICATION } from "../lib/rules/contentSpecs";
import { checkClientStatus } from "../lib/rules/clientStatus";
import { checkConsistency } from "../lib/rules/consistency";
import { AMOUNTS, ASSET, CONTRACT_NUMBER, GUARANTOR, PROVIDER, RECIPIENT, SUPPLIER } from "../lib/rules/consistencySpecs";
import { checkContents } from "../lib/rules/contents";
import { checkLoanAgreement } from "../lib/rules/loanAgreement";
import { checkRecipientMatch } from "../lib/rules/recipientMatch";
import { checkRequiredDocuments, toTypedRequirements } from "../lib/rules/requiredDocuments";
import type { DocumentRead, Run } from "../lib/run";
import { CASES, CASE_METADATA, type EvalCase } from "./cases";
import type { CaseDocument, Entity } from "./documents";

const reasoning = "Answer key check.";

const CONTENTS_SPECS = [INVOICE, PURCHASE_CONTRACT, HANDOVER_PROTOCOL, TECHNICAL_SPECIFICATION, PAYMENT_PROOF, SECURITY_TRANSFER, INSURANCE_VINCULATION, GUARANTEE];

const CONSISTENCY_SPECS: Array<[Entity, typeof RECIPIENT]> = [
  ["recipient", RECIPIENT],
  ["supplier", SUPPLIER],
  ["provider", PROVIDER],
  ["asset", ASSET],
  ["amounts", AMOUNTS],
  ["contract", CONTRACT_NUMBER],
  ["guarantor", GUARANTOR],
];

const REQUIREMENT_NAMES = {
  invoice: "daňový doklad dodavatele",
  purchase_contract: "kupní smlouva",
  handover_protocol: "předávací protokol",
  technical_specification: "technická specifikace",
  payment_proof: "výpis z účtu s úhradou DPH",
  security_transfer: "smlouva o zajišťovacím převodu vlastnického práva",
  insurance_vinculation: "vinkulace pojistného plnění",
  guarantee: "prohlášení o ručení",
  other: "jiný doklad",
};

function toRun(c: EvalCase): Run {
  const { client, documents } = c.fixture!;
  return {
    evaluation_id: `ev-${c.case_id}`,
    row_id: "row-1",
    case_id: c.case_id,
    is_mock: true,
    client: client && {
      name: client.name, ico: client.ico, dic: client.dic, address: client.address, status: client.status, signatories: client.signatories, kyc: client.kyc,
    },
    case_metadata: CASE_METADATA,
    documents: documents.map(({ document_id, title, label }) => ({ document_id, title, label })),
  };
}

// What get_document keeps in KV after reading the document.
function toRead(d: CaseDocument): DocumentRead {
  return {
    page_count: d.pages.length,
    empty_pages: d.pages.flatMap((text, i) => (text ? [] : [i + 1])),
    pages_failed: d.pages_failed,
    confidence: d.confidence,
    signatures: d.errors?.signatures ? null : d.signatures.map(({ role, page }) => ({ role, page })),
  };
}

// The expected status must be accepted; every other status rejected unless the case allows it.
function checkKey(c: EvalCase, rule: RuleId, statuses: Status[], check: (status: Status) => CheckOutcome) {
  const expected = c.expected?.[rule];
  if (!expected) return;
  const outcome = check(expected);
  expect(outcome.problems, `${c.slug}: ${rule} ${expected} is rejected`).toBeUndefined();
  expect(outcome.result?.status).toBe(expected);
  const accepted = statuses.filter((s) => s !== expected && !check(s).problems);
  expect(accepted, `${c.slug}: ${rule} also accepts`).toEqual(c.tool_also_accepts?.[rule] ?? []);
}

const withFixture = CASES.filter((c) => c.fixture && c.expected);

describe("eval cases", () => {
  it("have unique slugs and case IDs", () => {
    expect(new Set(CASES.map((c) => c.slug)).size).toBe(CASES.length);
    const fixtures = CASES.flatMap((c) => (c.fixture ? [c.fixture.case_id] : []));
    expect(new Set(fixtures).size).toBe(fixtures.length);
    for (const c of CASES.filter((c) => !c.fixture && c.case_id)) expect(fixtures, c.slug).toContain(c.case_id);
  });

  it.each(CASES.filter((c) => c.verdict).map((c) => [c.slug, c] as const))("%s: answer key covers every rule and gives the verdict", (_, c) => {
    // Judgment calls are left out, so the other statuses alone must decide the verdict.
    expect([...Object.keys(c.expected ?? {}), ...(c.judgment_calls ?? [])].sort()).toEqual([...RULE_IDS].sort());
    expect(getVerdict(Object.values(c.expected!))).toBe(c.verdict);
    expect(c.run).toBe("completed");
  });

  it.each(CASES.filter((c) => c.fixture).map((c) => [c.slug, c] as const))("%s: fields come from pages with text", (_, c) => {
    for (const d of c.fixture!.documents) {
      for (const [key, field] of Object.entries(d.fields)) {
        expect(d.pages[field.page - 1], `${d.title} ${key}`).toBeTruthy();
      }
    }
  });
});

describe.each(withFixture.map((c) => [c.slug, c] as const))("%s answer key", (_, c) => {
  const run = toRun(c);
  const docs = c.fixture!.documents;
  const reading = c.reading!;
  const agreement = docs.find((d) => d.label === "smlouva_o_uveru");
  const requirements = (reading.requirements ?? []).map((type) => {
    const match = docs.find((d) => d.types.includes(type));
    return { description: REQUIREMENT_NAMES[type], type, ...(match && { document_id: match.document_id }) };
  });

  it("loan_agreement_present", () => {
    // The tool can't tell an agreement from another document, so it accepts missing
    // whenever no document_id is given; only the expected status is checked.
    checkKey(c, "loan_agreement_present", [], (status) =>
      checkLoanAgreement(run, { status: status as "passed", document_id: status === "passed" ? agreement?.document_id : undefined, reasoning }));
  });

  it("required_documents_present", () => {
    checkKey(c, "required_documents_present", ["passed", "missing", "cannot_verify"], (status) =>
      checkRequiredDocuments(run, { status: status as "passed", requirements, reasoning }));
  });

  it("recipient_matches_client", () => {
    checkKey(c, "recipient_matches_client", ["passed", "conflict", "cannot_verify"], (status) =>
      checkRecipientMatch(run, {
        status: status as "passed",
        agreement_name: reading.recipient?.name,
        agreement_ico: reading.recipient?.ico,
        document_id: agreement?.document_id,
        page: 1,
        reasoning,
      }));
  });

  const status = !requirements.length ? "cannot_verify" : requirements.every((r) => r.document_id) ? "passed" : "missing";
  const recorded = checkRequiredDocuments(run, { status, requirements, reasoning });
  const typed = toTypedRequirements(recorded.result!.details);

  // The agent reads every document it can; one that fails to load has no values.
  const reads = new Map(docs.filter((d) => !d.errors?.get).map((d) => [d.document_id, toRead(d)]));
  const getRead = (id: string) => reads.get(id) ?? null;
  const mentions = (entity: Entity) => docs.filter((d) => reads.has(d.document_id)).flatMap((d) =>
    d.mentions.filter((x) => x.entity === entity).map((x) => ({ ...x, document_id: d.document_id })));

  it.each(CONSISTENCY_SPECS.map(([entity, spec]) => [spec.rule_id, entity, spec] as const))("%s", (_, entity, spec) => {
    const found = mentions(entity);
    const attributes = spec.attributes.map(({ key }) => {
      const values = found.filter((x) => x.attribute === key).map(({ document_id, page, value }) => ({ document_id, page, value }));
      // A document shows a value once per page.
      return { attribute: key, values: values.filter((v, i) => values.findIndex((w) => w.document_id === v.document_id && w.page === v.page && w.value === v.value) === i) };
    });
    const statuses: Status[] = spec.optional ? ["passed", "conflict", "cannot_verify", "not_applicable"] : ["passed", "conflict", "cannot_verify"];
    checkKey(c, spec.rule_id, statuses, (status) => checkConsistency(spec, run, getRead, { status: status as "passed", attributes, reasoning }));
  });

  it("client_status_valid", () => {
    const signatories = mentions("signatory").map(({ value, document_id, page }) => ({ name: value, document_id, page }));
    checkKey(c, "client_status_valid", ["passed", "conflict", "cannot_verify"], (status) =>
      checkClientStatus(run, getRead, { status: status as "passed", signatories, reasoning }));
  });

  it.each(CONTENTS_SPECS.map((spec) => [spec.rule_id, spec] as const))("%s", (_, spec) => {
    const matched = typed.find((r) => r.type === spec.document_type && r.document_id);
    const document = docs.find((d) => d.document_id === matched?.document_id);
    const read = document && !document.errors?.get ? toRead(document) : null;
    const fields = spec.fields.map(({ key }) => (document?.fields[key] ? { field: key, ...document.fields[key] } : { field: key }));
    // With no matched document there is nothing to send but the status.
    checkKey(c, spec.rule_id, ["passed", "missing", "cannot_verify", "not_applicable"], (status) =>
      checkContents(spec, run, typed, read, !document || status === "not_applicable"
        ? { status, reasoning }
        : { status: status as "passed", document_id: document.document_id, fields, reasoning }));
  });
});
