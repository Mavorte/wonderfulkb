import { s, w } from "@wonderful/types/schema";
import { recordRule } from "../../lib/record";
import { checkLoanAgreement } from "../../lib/rules/loanAgreement";

export default w.tool({
  name: "evaluate_loan_agreement_present",
  description: "Record rule loan_agreement_present: whether a loan agreement is among the case's documents.",
  params: s.object({
    status: s.enum("passed", "missing").describe("passed if a loan agreement (smlouva o úvěru) is among the documents, otherwise missing."),
    document_id: s.optional(s.string()).describe("The loan agreement's document_id. Required for passed; leave out for missing."),
    reasoning: s.string().describe("Why you chose this status: which document you identified as the agreement and how, or what you looked for."),
  }),
  handler: async (ctx, input) => recordRule(ctx, (run) => checkLoanAgreement(run, input)),
});
