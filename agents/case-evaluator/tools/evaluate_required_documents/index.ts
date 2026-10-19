import { s, w } from "@wonderful/types/schema";
import { recordRule } from "../../lib/record";
import { DOCUMENT_TYPES } from "../../lib/rules";
import { checkRequiredDocuments, toTypedRequirements } from "../../lib/rules/requiredDocuments";
import { saveRequirements } from "../../lib/run";

export default w.tool({
  name: "evaluate_required_documents",
  description:
    "Record rule required_documents_present: for each document the loan agreement requires before disbursement, its type and which uploaded document provides it. Record this before the *_contents rules, which check the documents matched here.",
  params: s.object({
    status: s.enum("passed", "missing", "cannot_verify").describe(
      "passed if every requirement has a matching document; missing if at least one has none; cannot_verify if the agreement's requirements can't be read (no agreement, unreadable text).",
    ),
    requirements: s
      .array(s.object({ description: s.string(), type: s.enum(...DOCUMENT_TYPES), document_id: s.optional(s.string()) }))
      .describe(
        'Every document the loan agreement requires before disbursement, in its order. description: short Czech name of the requirement as the agreement words it, e.g. "faktura (daňový doklad)"; never a letter or number. type: the kind of document, one of invoice, purchase_contract, handover_protocol, technical_specification, payment_proof, security_transfer, insurance_vinculation, guarantee, other. The matching *_contents rule checks the document of each type. document_id: the matching uploaded document, left out if none matches. Empty only for cannot_verify.',
      ),
    reasoning: s.string().describe("Why you matched (or did not match) each requirement to a document; mention anything borderline."),
  }),
  handler: async (ctx, input) =>
    recordRule(ctx, (run) => checkRequiredDocuments(run, input), (run, result) => saveRequirements(ctx, run, toTypedRequirements(result.details))),
});
