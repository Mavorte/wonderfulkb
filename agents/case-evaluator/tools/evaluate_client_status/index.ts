import { s, w } from "@wonderful/types/schema";
import { recordRule } from "../../lib/record";
import { checkClientStatus } from "../../lib/rules/clientStatus";
import { getDocumentRead } from "../../lib/run";

export default w.tool({
  name: "evaluate_client_status",
  description:
    "Record rule client_status_valid: the client record shows an active client with KYC ok, and the people signing for the recipient in the documents are its authorized signatories. The tool reads the client record itself and rejects your status if it disagrees.",
  params: s.object({
    status: s.enum("passed", "conflict", "cannot_verify").describe(
      "passed if the client is active, KYC is ok and everyone who signs for the recipient is an authorized signatory in the client record; conflict if any of these fails; cannot_verify only if there is no client record, or no document shows who signs for the recipient.",
    ),
    signatories: s
      .array(s.object({ name: s.string(), document_id: s.string(), page: s.number() }))
      .describe("Each person named as signing for the recipient (příjemce financování / kupující / úvěrovaný), as written, with the document's ref and page. Not the signatories of SGEF, the supplier or the guarantor."),
    reasoning: s.string().describe("Why you chose this status: the client's status and KYC, who signs and whether they are authorized."),
  }),
  handler: async (ctx, input) => recordRule(ctx, (run) => checkClientStatus(run, (id) => getDocumentRead(ctx, run, id), input)),
});
