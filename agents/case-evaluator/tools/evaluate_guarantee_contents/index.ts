import { s, w } from "@wonderful/types/schema";
import { recordRule } from "../../lib/record";
import { checkContents } from "../../lib/rules/contents";
import { GUARANTEE } from "../../lib/rules/contentSpecs";
import { getDocumentRead, getRequirements } from "../../lib/run";

export default w.tool({
  name: "evaluate_guarantee_contents",
  description:
    "Record rule guarantee_contents: whether the guarantee declaration shows the guarantor, SGEF as creditor, the recipient as debtor, the secured contract, scope, the guarantor's commitment and date, and is signed. Read the document with get_document first. The tool checks your status against the fields and the document's signatures, and rejects it if they disagree.",
  params: s.object({
    status: s.enum("passed", "missing", "cannot_verify", "not_applicable").describe(
      "passed if the guarantee declaration (prohlášení o ručení) shows every mandatory field and signature; missing if any is absent or blank; cannot_verify if the document is too hard to read to tell (pages_failed or low confidence). If required_documents_present matched no document of type guarantee, send no document_id or fields and use: missing if a guarantee requirement has no document (required but not uploaded); cannot_verify if required_documents_present listed no requirements; not_applicable if the agreement doesn't require one.",
    ),
    document_id: s.optional(s.string()).describe("The guarantee declaration (prohlášení o ručení) that required_documents_present matched. Leave out when no document was matched."),
    fields: s
      .optional(s.array(s.object({ field: s.enum("guarantor", "creditor", "debtor", "secured_contract", "scope", "commitment", "date"), value: s.optional(s.string()), page: s.optional(s.number()) })))
      .describe(
        "One entry per field, every field listed: field key, value as the document shows it (short), and its page. Leave out value (and page) when the document doesn't show the field. Leave out fields when no document was matched. Fields: guarantor: guarantor (ručitel); creditor: SGEF as creditor (věřitel); debtor: recipient as main debtor (příjemce financování); secured_contract: secured contract or debt (zajištěná smlouva); scope: scope of the guarantee (rozsah ručení); commitment: guarantor's commitment to pay (závazek ručitele plnit); date: date. The tool checks the signatures itself, from what get_document returned: guarantor (role guarantor), SGEF (two signatories) (role provider, 2 signatures).",
      ),
    reasoning: s.string().describe("Why you chose this status: what is there, what is missing or unreadable, and where."),
  }),
  handler: async (ctx, input) =>
    recordRule(ctx, (run) => checkContents(GUARANTEE, run, getRequirements(ctx, run), getDocumentRead(ctx, run, input.document_id), input)),
});
