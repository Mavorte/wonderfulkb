import { s, w } from "@wonderful/types/schema";
import { recordRule } from "../../lib/record";
import { checkRecipientMatch } from "../../lib/rules/recipientMatch";

export default w.tool({
  name: "evaluate_recipient_match",
  description:
    "Record rule recipient_matches_client: compare the recipient in the loan agreement with the client record. The tool checks your status against the values and rejects it if they disagree.",
  params: s.object({
    status: s.enum("passed", "conflict", "cannot_verify").describe(
      "passed if the agreement's recipient name and IČO match the client record; conflict if either differs (a placeholder or malformed IČO is a conflict); cannot_verify only if there is no client record or no readable recipient block.",
    ),
    agreement_name: s.optional(s.string()).describe("Recipient (příjemce financování) name exactly as written in the agreement."),
    agreement_ico: s.optional(s.string()).describe("Recipient IČ/IČO exactly as written in the agreement, even if it looks wrong."),
    document_id: s.optional(s.string()).describe("document_id of the loan agreement the values come from."),
    page: s.optional(s.number()).describe("Page of the agreement where the recipient block is."),
    reasoning: s.string().describe("Why you chose this status: what you compared and what differs, if anything."),
  }),
  handler: async (ctx, input) => recordRule(ctx, (run) => checkRecipientMatch(run, input)),
});
