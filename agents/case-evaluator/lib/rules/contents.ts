// Validator shared by the *_contents rules: one document of a given type must
// show its mandatory fields and signatures (business_rules.docx). The agent
// reports each field as read, with its page; the signatures come from what
// get_document loaded, not from the agent.

import type { DocumentType, RuleId } from "../rules";
import { type DocumentRead, type Run, type Source, type TypedRequirement, findDocument } from "../run";
import { FIELD_REGIONS, SIGNATURE_PARTIES } from "../regions";
import { type CheckOutcome, rejected, requireReasoning } from "./check";

// Signature roles of the documents API: provider is SGEF.
export type SignatureRole = "provider" | "borrower" | "supplier" | "guarantor" | "insurer";

const ROLES = new Set<string>(["provider", "borrower", "supplier", "guarantor", "insurer"]);

// Other names the documents API gives the same parties, e.g. buyer on an order.
const ROLE_ALIASES: Record<string, SignatureRole> = { buyer: "borrower", recipient: "borrower", seller: "supplier" };

export type FieldSpec = { key: string; label: string; optional?: boolean };

export type SignatureSpec = { role: SignatureRole; min: number; label: string };

export type ContentsSpec = {
  rule_id: RuleId;
  document_type: DocumentType;
  document_name: string;
  fields: FieldSpec[];
  signatures: SignatureSpec[];
};

export type ContentsInput = {
  status: "passed" | "missing" | "cannot_verify" | "not_applicable";
  document_id?: string;
  fields?: Array<{ field: string; value?: string; page?: number }>;
  reasoning: string;
};

// Below this OCR confidence a document counts as hard to read.
export const LOW_CONFIDENCE = 0.8;

export function checkContents(
  spec: ContentsSpec,
  run: Run,
  requirements: TypedRequirement[] | null,
  read: DocumentRead | null,
  input: ContentsInput,
): CheckOutcome {
  const problems: string[] = [];
  requireReasoning(input.reasoning, problems);
  if (!requirements) {
    return rejected([...problems, "Record required_documents_present first: the documents it matches decide what this rule checks."]);
  }
  const ofType = requirements.filter((r) => r.type === spec.document_type);
  const matched = [...new Set(ofType.map((r) => r.document_id).filter((id) => id !== null))];
  const titles = matched.map((id) => findDocument(run, id)?.title ?? id).join(", ");

  // No document to check: the status follows from required_documents_present.
  // An empty requirements list means it was cannot_verify (no readable agreement).
  if (!matched.length) {
    const [status, found, why] = !requirements.length
      ? ["cannot_verify", "Requirements unknown: no readable loan agreement", "required_documents_present lists no requirements, so it is unknown whether one is needed"] as const
      : ofType.length
        ? ["missing", "Required, but not uploaded; see required_documents_present", `required_documents_present has a requirement for the ${spec.document_name} with no document`] as const
        : ["not_applicable", "Not required by the loan agreement", `the loan agreement doesn't require a ${spec.document_name}`] as const;
    if (input.status !== status) problems.push(`status ${input.status}, but ${why}. Use status ${status} with no document_id or fields.`);
    else if (input.document_id || input.fields?.length) problems.push(`With no ${spec.document_name} to check, send no document_id or fields.`);
    if (problems.length) return rejected(problems);
    return {
      result: {
        rule_id: spec.rule_id,
        status,
        expected: `${spec.document_name}, if the loan agreement requires one`,
        found,
        sources: [],
        details: { required: status === "cannot_verify" ? null : ofType.length > 0, uploaded: false },
        reasoning: input.reasoning,
      },
    };
  }

  if (input.status === "not_applicable") {
    problems.push(`status not_applicable, but required_documents_present matched the ${spec.document_name} requirement to ${titles}. Check that document.`);
  }
  const document = input.document_id ? findDocument(run, input.document_id) : undefined;
  if (!input.document_id) problems.push(`Give the document_id of the ${spec.document_name} you checked.`);
  else if (!document) problems.push(`document_id "${input.document_id}" is not a document of this case.`);
  else if (matched.length && !matched.includes(document.document_id)) {
    problems.push(`document_id must be the document matched to the ${spec.document_name} requirement in required_documents_present: ${titles}.`);
  }
  if (document && !read) problems.push("Read this document with get_document first.");

  const keys = spec.fields.map((f) => f.key);
  const values = new Map<string, { value: string; page?: number }>();
  for (const f of input.fields ?? []) {
    if (!keys.includes(f.field)) {
      problems.push(`"${f.field}" is not a field of this rule; the fields are ${keys.join(", ")}.`);
      continue;
    }
    if (values.has(f.field)) problems.push(`Field ${f.field} is listed twice.`);
    const value = f.value?.trim() ?? "";
    values.set(f.field, { value, page: f.page });
    if (!value) continue;
    if (f.page === undefined) problems.push(`Field ${f.field}: give the page the value is on.`);
    else if (read && (f.page < 1 || f.page > read.page_count)) problems.push(`Field ${f.field}: page ${f.page} is not a page of this document (1-${read.page_count}).`);
    else if (read?.empty_pages.includes(f.page)) problems.push(`Field ${f.field}: page ${f.page} has no text, so the value can't come from it.`);
  }
  const unlisted = keys.filter((k) => !values.has(k));
  if (unlisted.length) problems.push(`List every field, leaving out value when the document doesn't show it. Not listed: ${unlisted.join(", ")}.`);
  if (problems.length || !read || !document) return rejected(problems);

  const absentFields = spec.fields.filter((f) => !f.optional && !values.get(f.key)?.value);
  const signaturesKnown = read.signatures !== null;
  // A signature whose role the documents API couldn't assign (e.g. "unknown") may
  // be anyone's, so it makes up a missing signature of any role.
  const detected = (read.signatures ?? []).map((s) => ({ ...s, role: ROLE_ALIASES[s.role] ?? s.role }));
  const unassigned = detected.filter((s) => !ROLES.has(s.role));
  const signatures = spec.signatures.map((sig) => {
    if (!signaturesKnown) return { ...sig, found: null, unassigned: 0, pages: [] as number[] };
    const found = detected.filter((s) => s.role === sig.role);
    const filled = unassigned.splice(0, Math.max(0, sig.min - found.length));
    return { ...sig, found: found.length + filled.length, unassigned: filled.length, pages: [...new Set([...found, ...filled].map((s) => s.page))] };
  });
  const shortSignatures = signatures.filter((s) => s.found !== null && s.found < s.min);
  const absent = [
    ...absentFields.map((f) => f.label),
    ...shortSignatures.map((s) => `${s.label} signature (${s.found} of ${s.min})`),
  ];
  const signaturesUnknown = !signaturesKnown && spec.signatures.length > 0;
  const hardToRead = read.pages_failed.length > 0 || (read.confidence ?? 1) < LOW_CONFIDENCE || signaturesUnknown;

  if (input.status === "passed") {
    if (absent.length) problems.push(`status passed, but these are missing: ${absent.join("; ")}. Use missing, or cannot_verify if the document is unreadable.`);
    if (signaturesUnknown) problems.push("status passed, but the signatures could not be loaded. Use cannot_verify.");
  }
  if (input.status === "missing" && !absent.length) {
    problems.push(signaturesUnknown
      ? "status missing, but every field is present and the signatures could not be loaded. Use cannot_verify."
      : "status missing, but every field and signature is present. Use passed.");
  }
  if (input.status === "cannot_verify") {
    if (!hardToRead) {
      problems.push(`status cannot_verify needs a document that is hard to read (pages_failed, confidence below ${LOW_CONFIDENCE}, or signatures not loaded); this one is readable, so use passed or missing. A page with no text that isn't in pages_failed is blank.`);
    } else if (!absent.length && !signaturesUnknown) {
      problems.push("status cannot_verify, but every field and signature is present. Use passed.");
    }
  }
  if (problems.length) return rejected(problems);

  // Each field value where it was read, the signature pages, then one source per
  // missing field or signature, pointing at where it should be when the regions tell.
  const at = { document_id: document.document_id, title: document.title };
  const shown: Source[] = [
    ...spec.fields.flatMap((f) => {
      const v = values.get(f.key);
      return v?.value && v.page !== undefined ? [{ ...at, page: v.page, role: "evidence", field: f.key, locate: { value: v.value, ...FIELD_REGIONS[f.key] } }] : [];
    }),
    ...[...new Set(signatures.flatMap((s) => s.pages))].map((page) => ({ ...at, page, role: "evidence" })),
  ];
  const sources: Source[] = [
    ...shown.sort((a, b) => (a.page ?? 0) - (b.page ?? 0)),
    ...absentFields.map((f) => ({ ...at, role: "missing_value", field: f.key, issue: f.label, locate: FIELD_REGIONS[f.key]?.parties ? FIELD_REGIONS[f.key] : {} })),
    ...shortSignatures.map((s) => ({ ...at, role: "missing_value", issue: `${s.label} signature`, locate: { labels: ["podpisovy_blok"], parties: SIGNATURE_PARTIES[s.role] } })),
  ];
  const expected = [
    ...spec.fields.map((f) => (f.optional ? `${f.label} (if any)` : f.label)),
    ...spec.signatures.map((s) => `${s.label} signature${s.min > 1 ? ` (${s.min})` : ""}`),
  ].join("; ");
  let found = absent.length ? `Missing: ${absent.join("; ")}` : "All mandatory contents and signatures present";
  if (signaturesUnknown) found += absent.length ? "; signatures not available" : ", but signatures not available";
  const byUnassigned = signatures.filter((s) => s.unassigned > 0).map((s) => s.label);
  if (byUnassigned.length) found += ` (signatures without a detected role counted as ${byUnassigned.join(", ")}; check visually)`;
  return {
    result: {
      rule_id: spec.rule_id,
      status: input.status,
      expected,
      found,
      sources,
      details: {
        document_id: document.document_id,
        fields: spec.fields.map((f) => ({ field: f.key, value: values.get(f.key)?.value || null, page: values.get(f.key)?.value ? values.get(f.key)?.page ?? null : null })),
        signatures: signatures.map(({ role, min, found: count, unassigned: fromUnassigned, pages: sigPages }) => ({ role, required: min, found: count, without_role: fromUnassigned, pages: sigPages })),
        confidence: read.confidence,
        pages_failed: read.pages_failed,
      },
      reasoning: input.reasoning,
    },
  };
}
