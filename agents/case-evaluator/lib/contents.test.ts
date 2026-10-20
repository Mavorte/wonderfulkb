import { describe, expect, it } from "vitest";
import { GUARANTEE, PURCHASE_CONTRACT, TECHNICAL_SPECIFICATION } from "./rules/contentSpecs";
import { type ContentsInput, checkContents } from "./rules/contents";
import type { DocumentRead, TypedRequirement } from "./run";
import { RUN } from "./testContext";

const reasoning = "because";

const REQUIREMENTS: TypedRequirement[] = [
  { type: "purchase_contract", document_id: "ord" },
  { type: "guarantee", document_id: "ruc" },
  { type: "invoice", document_id: null },
];

const run = { ...RUN, documents: [...RUN.documents, { document_id: "ruc", title: "4_Form_Ruceni.pdf", label: "ruceni" }] };

const READ: DocumentRead = {
  page_count: 3,
  empty_pages: [3],
  pages_failed: [],
  confidence: 0.98,
  signatures: [{ role: "guarantor", page: 2 }, { role: "provider", page: 2 }, { role: "provider", page: 2 }],
};

const ALL_FIELDS = GUARANTEE.fields.map((f) => ({ field: f.key, value: `${f.key} value`, page: 1 }));

const guarantee = (input: Partial<ContentsInput>, read: DocumentRead | null = READ, requirements: TypedRequirement[] | null = REQUIREMENTS) =>
  checkContents(GUARANTEE, run, requirements, read, { status: "passed", document_id: "ruc", fields: ALL_FIELDS, reasoning, ...input });

describe("checkContents", () => {
  it("passes a complete, signed document and cites its pages", () => {
    const { result } = guarantee({});
    expect(result).toMatchObject({ rule_id: "guarantee_contents", status: "passed", found: "All mandatory contents and signatures present" });
    expect([...new Set(result?.sources.map((s) => s.page))]).toEqual([1, 2]);
    expect(result?.details).toMatchObject({ signatures: [{ role: "guarantor", required: 1, found: 1 }, { role: "provider", required: 2, found: 2 }] });
  });

  it("needs required_documents_present first", () => {
    expect(guarantee({}, READ, null).problems?.at(-1)).toMatch(/Record required_documents_present first/);
  });

  it("records a missing field and a missing second SGEF signatory, and rejects passed for them", () => {
    const fields = ALL_FIELDS.map((f) => (f.field === "commitment" ? { field: f.field } : f));
    const read = { ...READ, signatures: READ.signatures!.slice(0, 2) };
    expect(guarantee({ status: "passed", fields }, read).problems?.[0]).toMatch(/these are missing: guarantor's commitment/);
    const { result } = guarantee({ status: "missing", fields }, read);
    expect(result?.found).toBe("Missing: guarantor's commitment to pay (závazek ručitele plnit); SGEF (two signatories) signature (1 of 2)");
  });

  it("rejects missing when everything is there", () => {
    expect(guarantee({ status: "missing" }).problems?.[0]).toMatch(/Use passed/);
  });

  it("requires every field to be listed, known and from a page with text", () => {
    const problems = guarantee({ fields: [...ALL_FIELDS.slice(1, -1), { field: "date", value: "1.1.2025", page: 3 }, { field: "colour", value: "red", page: 1 }] }).problems?.join("\n");
    expect(problems).toMatch(/"colour" is not a field/);
    expect(problems).toMatch(/page 3 has no text/);
    expect(problems).toMatch(/Not listed: guarantor/);
    expect(guarantee({ fields: [{ field: "guarantor", value: "SOLOM a.s." }, ...ALL_FIELDS.slice(1)] }).problems?.[0]).toMatch(/give the page/);
    expect(guarantee({ fields: [{ field: "guarantor", value: "SOLOM a.s.", page: 9 }, ...ALL_FIELDS.slice(1)] }).problems?.[0]).toMatch(/not a page of this document/);
  });

  it("checks the document against the required_documents_present mapping", () => {
    expect(guarantee({ document_id: "ord" }).problems?.[0]).toMatch(/must be the document matched .*4_Form_Ruceni.pdf/);
    expect(guarantee({ status: "not_applicable", document_id: undefined, fields: undefined }).problems?.[0]).toMatch(/matched the guarantee declaration .* requirement to 4_Form_Ruceni.pdf/);
    expect(guarantee({}, null).problems?.[0]).toMatch(/get_document first/);
  });

  it("allows not_applicable only when the agreement doesn't require the document", () => {
    const notRequired = checkContents(TECHNICAL_SPECIFICATION, run, REQUIREMENTS, null, { status: "not_applicable", reasoning });
    expect(notRequired.result).toMatchObject({ status: "not_applicable", found: "Not required by the loan agreement", details: { required: false, uploaded: false } });
    const passed = checkContents(TECHNICAL_SPECIFICATION, run, REQUIREMENTS, READ, { status: "passed", document_id: "ruc", fields: [], reasoning });
    expect(passed.problems?.[0]).toMatch(/doesn't require a technical specification.*Use status not_applicable/);
  });

  it("records a required but not uploaded document as missing", () => {
    const invoice = { ...TECHNICAL_SPECIFICATION, document_type: "invoice" as const, document_name: "invoice" };
    const notUploaded = checkContents(invoice, run, REQUIREMENTS, null, { status: "missing", reasoning });
    expect(notUploaded.result).toMatchObject({ status: "missing", found: "Required, but not uploaded; see required_documents_present", sources: [], details: { required: true, uploaded: false } });
    const notApplicable = checkContents(invoice, run, REQUIREMENTS, null, { status: "not_applicable", reasoning });
    expect(notApplicable.problems?.[0]).toMatch(/has a requirement for the invoice with no document\. Use status missing/);
    const withFields = checkContents(invoice, run, REQUIREMENTS, null, { status: "missing", document_id: "ord", reasoning });
    expect(withFields.problems?.[0]).toMatch(/send no document_id or fields/);
  });

  it("records cannot_verify when there are no requirements (no readable agreement)", () => {
    const unknown = guarantee({ status: "cannot_verify", document_id: undefined, fields: undefined }, null, []);
    expect(unknown.result).toMatchObject({ status: "cannot_verify", found: "Requirements unknown: no readable loan agreement", details: { required: null, uploaded: false } });
    expect(guarantee({ status: "not_applicable", document_id: undefined, fields: undefined }, null, []).problems?.[0]).toMatch(/lists no requirements.*Use status cannot_verify/);
  });

  it("allows cannot_verify only for a hard-to-read document", () => {
    const fields = ALL_FIELDS.map((f) => (f.field === "scope" ? { field: f.field } : f));
    expect(guarantee({ status: "cannot_verify", fields }).problems?.[0]).toMatch(/needs a document that is hard to read/);
    expect(guarantee({ status: "cannot_verify", fields }, { ...READ, confidence: 0.55 }).result?.status).toBe("cannot_verify");
    expect(guarantee({ status: "cannot_verify" }, { ...READ, confidence: 0.55 }).problems?.[0]).toMatch(/every field and signature is present/);
  });

  it("asks for cannot_verify when the signatures could not be loaded", () => {
    const read = { ...READ, signatures: null };
    expect(guarantee({}, read).problems?.[0]).toMatch(/signatures could not be loaded/);
    expect(guarantee({ status: "cannot_verify" }, read).result?.found).toBe("All mandatory contents and signatures present, but signatures not available");
  });

  it("ignores optional fields and counts each signature role", () => {
    const run2 = { ...run, documents: [...run.documents, { document_id: "ts", title: "TS.pdf", label: "x" }] };
    const read = { ...READ, empty_pages: [], signatures: [] };
    const fields = TECHNICAL_SPECIFICATION.fields.map((f) => (f.optional ? { field: f.key } : { field: f.key, value: "x", page: 1 }));
    const ts = checkContents(TECHNICAL_SPECIFICATION, run2, [{ type: "technical_specification", document_id: "ts" }], read, { status: "passed", document_id: "ts", fields, reasoning });
    expect(ts.result?.status).toBe("passed");
    const order = PURCHASE_CONTRACT.fields.map((f) => ({ field: f.key, value: "x", page: 1 }));
    const signed = { ...read, signatures: [{ role: "borrower", page: 1 }] };
    const outcome = checkContents(PURCHASE_CONTRACT, run, REQUIREMENTS, signed, { status: "missing", document_id: "ord", fields: order, reasoning });
    expect(outcome.result?.found).toBe("Missing: seller (signature or confirmation) signature (0 of 1)");
  });

  it("counts buyer as the borrower and seller as the supplier", () => {
    const order = PURCHASE_CONTRACT.fields.map((f) => ({ field: f.key, value: "x", page: 1 }));
    const read = { ...READ, empty_pages: [], signatures: [{ role: "buyer", page: 2 }, { role: "seller", page: 2 }] };
    const { result } = checkContents(PURCHASE_CONTRACT, run, REQUIREMENTS, read, { status: "passed", document_id: "ord", fields: order, reasoning });
    expect(result?.found).toBe("All mandatory contents and signatures present");
  });

  it("lets signatures without a role make up missing ones, and says so", () => {
    const order = PURCHASE_CONTRACT.fields.map((f) => ({ field: f.key, value: "x", page: 1 }));
    const read = { ...READ, empty_pages: [], signatures: [{ role: "unknown", page: 2 }, { role: "supplier", page: 2 }] };
    const { result } = checkContents(PURCHASE_CONTRACT, run, REQUIREMENTS, read, { status: "passed", document_id: "ord", fields: order, reasoning });
    expect(result?.found).toBe("All mandatory contents and signatures present (signatures without a detected role counted as buyer; check visually)");
    expect(result?.details).toMatchObject({ signatures: [{ role: "borrower", found: 1, without_role: 1 }, { role: "supplier", found: 1, without_role: 0 }] });
    const one = { ...read, signatures: [{ role: "unknown", page: 2 }] };
    const missing = checkContents(PURCHASE_CONTRACT, run, REQUIREMENTS, one, { status: "missing", document_id: "ord", fields: order, reasoning });
    expect(missing.result?.found).toMatch(/^Missing: seller \(signature or confirmation\) signature \(0 of 1\) \(signatures without a detected role counted as buyer/);
  });
});
