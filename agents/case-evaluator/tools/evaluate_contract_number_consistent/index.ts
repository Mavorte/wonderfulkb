import { s, w } from "@wonderful/types/schema";
import { recordRule } from "../../lib/record";
import { checkGroupedConsistency } from "../../lib/rules/consistency";
import { CONTRACT_NUMBER } from "../../lib/rules/consistencySpecs";
import { getDocumentRead } from "../../lib/run";

export default w.tool({
  name: "evaluate_contract_number_consistent",
  description:
    "Record rule contract_number_consistent: whether every document that refers to the loan contract gives the same number as the case record. Give each distinct value with the places it appears; read each document with get_document first. The tool normalizes and compares the values, and rejects your status if they disagree.",
  params: s.object({
    status: s.enum("passed", "conflict", "cannot_verify").describe(
      "passed if every value of the loan contract number agrees; conflict if any differs or is malformed (e.g. an IČO without 8 digits); cannot_verify only if no attribute appears in two sources.",
    ),
    attributes: s
      .optional(
        s.array(
          s.object({
            attribute: s.enum("loan_number"),
            values: s.array(s.object({ value: s.string(), at: s.array(s.string()) })),
          }),
        ),
      )
      .describe(
        "One entry per attribute, every attribute listed. values: each distinct value of the loan contract number once, exactly as written, with every place it appears in at as <ref>:<page> (e.g. \"D3:1\"). Only values written identically (spacing aside) share an entry; any other difference is a separate entry, because the tool does the comparing. Use an empty values list when no document shows the attribute. Leave out attributes for not_applicable. Attributes: loan_number: loan contract number. The tool adds the reference values itself (the client record or the case record); don't list them.",
      ),
    reasoning: s.string().describe("Why you chose this status: what you compared, what differs and where, and any values you judged equivalent."),
  }),
  handler: async (ctx, input) => recordRule(ctx, (run) => checkGroupedConsistency(CONTRACT_NUMBER, run, (id) => getDocumentRead(ctx, run, id), input)),
});
