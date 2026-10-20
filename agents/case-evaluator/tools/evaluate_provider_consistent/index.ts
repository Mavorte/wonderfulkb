import { s, w } from "@wonderful/types/schema";
import { recordRule } from "../../lib/record";
import { checkGroupedConsistency } from "../../lib/rules/consistency";
import { PROVIDER } from "../../lib/rules/consistencySpecs";
import { getDocumentRead } from "../../lib/run";

export default w.tool({
  name: "evaluate_provider_consistent",
  description:
    "Record rule provider_consistent: whether the provider (poskytovatel financování) has the same name, IČO, DIČ and bank account in every document that names it. Give each distinct value with the places it appears; read each document with get_document first. The tool normalizes and compares the values, and rejects your status if they disagree.",
  params: s.object({
    status: s.enum("passed", "conflict", "cannot_verify").describe(
      "passed if every value of the provider (poskytovatel financování) agrees; conflict if any differs or is malformed (e.g. an IČO without 8 digits); cannot_verify only if no attribute appears in two sources.",
    ),
    attributes: s
      .optional(
        s.array(
          s.object({
            attribute: s.enum("name", "ico", "dic", "bank_account"),
            values: s.array(s.object({ value: s.string(), at: s.array(s.string()) })),
          }),
        ),
      )
      .describe(
        "One entry per attribute, every attribute listed. values: each distinct value of the provider (poskytovatel financování) once, exactly as written, with every place it appears in at as <ref>:<page> (e.g. \"D3:1\"). Only values written identically (spacing aside) share an entry; any other difference is a separate entry, because the tool does the comparing. Use an empty values list when no document shows the attribute. Leave out attributes for not_applicable. Attributes: name: name; ico: IČO; dic: DIČ; bank_account: bank account.",
      ),
    equivalent: s
      .optional(s.array(s.enum("name")))
      .describe(
        "Text attributes whose values differ only in how they are written (word order, abbreviations, a short vs a full asset name), so you judge them to be the same. Explain why in reasoning. A different company or street is a conflict, not equivalent. Identifiers and numbers can't be listed: they must match exactly.",
      ),
    reasoning: s.string().describe("Why you chose this status: what you compared, what differs and where, and any values you judged equivalent."),
  }),
  handler: async (ctx, input) => recordRule(ctx, (run) => checkGroupedConsistency(PROVIDER, run, (id) => getDocumentRead(ctx, run, id), input)),
});
