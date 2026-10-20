import { s, w } from "@wonderful/types/schema";
import { recordRule } from "../../lib/record";
import { checkGroupedConsistency } from "../../lib/rules/consistency";
import { AMOUNTS } from "../../lib/rules/consistencySpecs";
import { getDocumentRead } from "../../lib/run";

export default w.tool({
  name: "evaluate_amounts_consistent",
  description:
    "Record rule amounts_consistent: whether the price without VAT, VAT, price with VAT and loan amount are the same in every document that states them. Give each distinct value with the places it appears; read each document with get_document first. The tool normalizes and compares the values, and rejects your status if they disagree.",
  params: s.object({
    status: s.enum("passed", "conflict", "cannot_verify").describe(
      "passed if every value of the price and loan amount agrees; conflict if any differs or is malformed (e.g. an IČO without 8 digits); cannot_verify only if no attribute appears in two sources.",
    ),
    attributes: s
      .optional(
        s.array(
          s.object({
            attribute: s.enum("price", "vat", "price_with_vat", "loan_amount"),
            values: s.array(s.object({ value: s.string(), at: s.array(s.string()) })),
          }),
        ),
      )
      .describe(
        "One entry per attribute, every attribute listed. values: each distinct value of the price and loan amount once, exactly as written, with every place it appears in at as <ref>:<page> (e.g. \"D3:1\"). Only values written identically (spacing aside) share an entry; any other difference is a separate entry, because the tool does the comparing. Use an empty values list when no document shows the attribute. Leave out attributes for not_applicable. Attributes: price: price without VAT; vat: VAT amount; price_with_vat: price with VAT; loan_amount: loan amount.",
      ),
    reasoning: s.string().describe("Why you chose this status: what you compared, what differs and where, and any values you judged equivalent."),
  }),
  handler: async (ctx, input) => recordRule(ctx, (run) => checkGroupedConsistency(AMOUNTS, run, (id) => getDocumentRead(ctx, run, id), input)),
});
