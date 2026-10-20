import { DOCUMENT_TYPES, type DocumentType } from "../rules";
import { type Run, type Source, type TypedRequirement, findDocument } from "../run";
import { REQUIRED_REFERS_TO } from "../regions";
import { type CheckOutcome, rejected, requireReasoning } from "./check";

export type Requirement = { description: string; type: DocumentType; document_id?: string };

export type RequiredDocumentsInput = {
  status: "passed" | "missing" | "cannot_verify";
  requirements: Requirement[];
  reasoning: string;
};

export function checkRequiredDocuments(run: Run, input: RequiredDocumentsInput): CheckOutcome {
  const problems: string[] = [];
  requireReasoning(input.reasoning, problems);
  const descriptions = new Set<string>();
  for (const r of input.requirements) {
    const description = r.description.trim();
    if (!description) problems.push("Each requirement needs a description.");
    if (descriptions.has(description)) problems.push(`Requirement "${description}" is listed twice.`);
    descriptions.add(description);
    if (!DOCUMENT_TYPES.includes(r.type)) problems.push(`Requirement "${description}": type must be one of ${DOCUMENT_TYPES.join(", ")}.`);
    if (r.document_id && !findDocument(run, r.document_id)) {
      problems.push(`Requirement "${description}": document_id "${r.document_id}" is not a document of this case.`);
    }
  }
  const unmatched = input.requirements.filter((r) => !r.document_id);
  if (input.status === "cannot_verify" && input.requirements.length) {
    problems.push("status cannot_verify is for when the requirements can't be read; then send an empty requirements list.");
  }
  if (input.status !== "cannot_verify" && !input.requirements.length) {
    problems.push("List every requirement from the loan agreement, or use status cannot_verify if you can't read them.");
  }
  if (input.status === "passed" && unmatched.length) {
    problems.push(`status passed, but these requirements have no document: ${unmatched.map((r) => r.description).join("; ")}.`);
  }
  if (input.status === "missing" && input.requirements.length && !unmatched.length) {
    problems.push("status missing, but every requirement has a document.");
  }
  if (problems.length) return rejected(problems);

  const label = (r: Requirement) => r.description.trim();
  const matched: Source[] = input.requirements
    .map((r) => (r.document_id ? findDocument(run, r.document_id) : undefined))
    .filter((d) => d !== undefined)
    .map((d) => ({ document_id: d.document_id, title: d.title }));
  // Each requirement without a document points at the agreement's clause that requires it.
  const agreement = run.documents.find((d) => d.label === "smlouva_o_uveru");
  const declarations: Source[] = agreement
    ? unmatched.map((r) => ({
      document_id: agreement.document_id,
      title: agreement.title,
      role: "declaration",
      issue: label(r),
      locate: { labels: ["povinny_podklad"], ...(REQUIRED_REFERS_TO[r.type] ? { refers_to: REQUIRED_REFERS_TO[r.type] } : { value: label(r) }) },
    }))
    : [];
  return {
    result: {
      rule_id: "required_documents_present",
      status: input.status,
      expected: input.requirements.map(label).join("; ") || "The loan agreement's list of required documents",
      found: input.status === "cannot_verify"
        ? "Requirements could not be read"
        : unmatched.length ? `No document for: ${unmatched.map(label).join("; ")}` : "Every requirement has a document",
      sources: [...matched.filter((s, i) => matched.findIndex((t) => t.document_id === s.document_id) === i), ...declarations],
      details: input.requirements.map((r) => ({
        description: r.description.trim(),
        type: r.type,
        document_id: findDocument(run, r.document_id)?.document_id ?? null,
        title: findDocument(run, r.document_id)?.title ?? null,
      })),
      reasoning: input.reasoning,
    },
  };
}

// The typed mapping the *_contents rules check against, from a saved result.
export function toTypedRequirements(details: unknown): TypedRequirement[] {
  return (details as Array<{ type: DocumentType; document_id: string | null }>).map(({ type, document_id }) => ({ type, document_id }));
}
