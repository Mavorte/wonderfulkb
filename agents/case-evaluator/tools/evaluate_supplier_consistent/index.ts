import { s, w } from "@wonderful/types/schema";
import { recordRule } from "../../lib/record";
import { checkConsistency } from "../../lib/rules/consistency";
import { SUPPLIER } from "../../lib/rules/consistencySpecs";
import { getDocumentRead } from "../../lib/run";

export default w.tool({
  name: "evaluate_supplier_consistent",
  description:
    "Record rule supplier_consistent: whether the supplier (dodavatel) has the same name, IČO, DIČ, address and bank account in every document that names it. Give the value each document shows, with its page; read each document with get_document first. The tool normalizes and compares the values, and rejects your status if they disagree.",
  params: s.object({
    status: s.enum("passed", "conflict", "cannot_verify").describe(
      "passed if every value of the supplier (dodavatel) agrees; conflict if any differs or is malformed (e.g. an IČO without 8 digits); cannot_verify only if no attribute appears in two sources.",
    ),
    attributes: s
      .optional(
        s.array(
          s.object({
            attribute: s.enum("name", "ico", "dic", "address", "bank_account"),
            values: s.array(s.object({ document_id: s.string(), page: s.number(), value: s.string() })),
          }),
        ),
      )
      .describe(
        "One entry per attribute, every attribute listed: the value each document shows for the supplier (dodavatel), exactly as written, with its document_id and page. A document may appear more than once if it shows the value on several pages. Use an empty values list when no document shows the attribute. Leave out attributes for not_applicable. Attributes: name: name; ico: IČO; dic: DIČ; address: address (sídlo); bank_account: bank account.",
      ),
    equivalent: s
      .optional(s.array(s.enum("name", "address")))
      .describe(
        "Text attributes whose values differ only in how they are written (word order, abbreviations, a short vs a full asset name), so you judge them to be the same. Explain why in reasoning. A different company or street is a conflict, not equivalent. Identifiers and numbers can't be listed: they must match exactly.",
      ),
    reasoning: s.string().describe("Why you chose this status: what you compared, what differs and where, and any values you judged equivalent."),
  }),
  handler: async (ctx, input) => recordRule(ctx, (run) => checkConsistency(SUPPLIER, run, (id) => getDocumentRead(ctx, run, id), input)),
});
