import { type Run, findDocument } from "../run";
import { type CheckOutcome, rejected, requireReasoning } from "./check";

export type LoanAgreementInput = {
  status: "passed" | "missing";
  document_id?: string;
  reasoning: string;
};

export function checkLoanAgreement(run: Run, input: LoanAgreementInput): CheckOutcome {
  const problems: string[] = [];
  requireReasoning(input.reasoning, problems);
  const document = input.document_id ? findDocument(run, input.document_id) : undefined;
  if (input.status === "passed" && !input.document_id) problems.push("status passed needs the document_id of the loan agreement.");
  if (input.document_id && !document) problems.push(`document_id "${input.document_id}" is not a document of this case.`);
  if (input.status === "missing" && input.document_id) problems.push("status missing must not have a document_id.");
  if (problems.length) return rejected(problems);
  return {
    result: {
      rule_id: "loan_agreement_present",
      status: input.status,
      expected: "Smlouva o úvěru",
      found: document ? document.title : `No loan agreement among ${run.documents.length} documents`,
      sources: document ? [{ document_id: document.document_id, title: document.title }] : [],
      reasoning: input.reasoning,
    },
  };
}
