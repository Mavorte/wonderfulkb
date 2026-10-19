import { s, w } from "@wonderful/types/schema";
import { recordRule } from "../../lib/record";
import { checkContents } from "../../lib/rules/contents";
import { SECURITY_TRANSFER } from "../../lib/rules/contentSpecs";
import { getDocumentRead, getRequirements } from "../../lib/run";

export default w.tool({
  name: "evaluate_security_transfer_contents",
  description:
    "Record rule security_transfer_contents: whether the security transfer of ownership shows SGEF, the recipient, the secured contract, the asset with serial number and value, the transfer terms and date, and is signed. Read the document with get_document first. The tool checks your status against the fields and the document's signatures, and rejects it if they disagree.",
  params: s.object({
    status: s.enum("passed", "missing", "cannot_verify", "not_applicable").describe(
      "passed if the security transfer of ownership (smlouva o zajišťovacím převodu vlastnického práva) shows every mandatory field and signature; missing if any is absent or blank; cannot_verify if the document is too hard to read to tell (pages_failed or low confidence). If required_documents_present matched no document of type security_transfer, send no document_id or fields and use: missing if a security_transfer requirement has no document (required but not uploaded); cannot_verify if required_documents_present listed no requirements; not_applicable if the agreement doesn't require one.",
    ),
    document_id: s.optional(s.string()).describe("The security transfer of ownership (smlouva o zajišťovacím převodu vlastnického práva) that required_documents_present matched. Leave out when no document was matched."),
    fields: s
      .optional(s.array(s.object({ field: s.enum("creditor", "debtor", "secured_contract", "asset", "serial_number", "asset_value", "transfer_terms", "date"), value: s.optional(s.string()), page: s.optional(s.number()) })))
      .describe(
        "One entry per field, every field listed: field key, value as the document shows it (short), and its page. Leave out value (and page) when the document doesn't show the field. Leave out fields when no document was matched. Fields: creditor: SGEF as creditor (věřitel); debtor: recipient as debtor (příjemce financování / dlužník); secured_contract: secured loan agreement number (zajišťovaná smlouva); asset: asset (předmět zajištění); serial_number: asset serial number (výrobní číslo); asset_value: asset value (hodnota); transfer_terms: transfer of ownership and the terms of its duration and return; date: date of signing. The tool checks the signatures itself, from what get_document returned: SGEF (two signatories) (role provider, 2 signatures), recipient (role borrower).",
      ),
    reasoning: s.string().describe("Why you chose this status: what is there, what is missing or unreadable, and where."),
  }),
  handler: async (ctx, input) =>
    recordRule(ctx, (run) => checkContents(SECURITY_TRANSFER, run, getRequirements(ctx, run), getDocumentRead(ctx, run, input.document_id), input)),
});
