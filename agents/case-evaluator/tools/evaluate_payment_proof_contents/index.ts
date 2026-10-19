import { s, w } from "@wonderful/types/schema";
import { recordRule } from "../../lib/record";
import { checkContents } from "../../lib/rules/contents";
import { PAYMENT_PROOF } from "../../lib/rules/contentSpecs";
import { getDocumentRead, getRequirements } from "../../lib/run";

export default w.tool({
  name: "evaluate_payment_proof_contents",
  description:
    "Record rule payment_proof_contents: whether the bank statement or payment proof shows both accounts, amount, currency, date and a link to the invoice or financing. Read the document with get_document first. The tool checks your status against the fields and the document's signatures, and rejects it if they disagree.",
  params: s.object({
    status: s.enum("passed", "missing", "cannot_verify", "not_applicable").describe(
      "passed if the bank statement or payment proof (výpis z účtu, potvrzení o úhradě) shows every mandatory field and signature; missing if any is absent or blank; cannot_verify if the document is too hard to read to tell (pages_failed or low confidence). If required_documents_present matched no document of type payment_proof, send no document_id or fields and use: missing if a payment_proof requirement has no document (required but not uploaded); cannot_verify if required_documents_present listed no requirements; not_applicable if the agreement doesn't require one.",
    ),
    document_id: s.optional(s.string()).describe("The bank statement or payment proof (výpis z účtu, potvrzení o úhradě) that required_documents_present matched. Leave out when no document was matched."),
    fields: s
      .optional(s.array(s.object({ field: s.enum("payer_account", "payee_account", "amount", "currency", "date", "reference"), value: s.optional(s.string()), page: s.optional(s.number()) })))
      .describe(
        "One entry per field, every field listed: field key, value as the document shows it (short), and its page. Leave out value (and page) when the document doesn't show the field. Leave out fields when no document was matched. Fields: payer_account: payer's account (účet plátce); payee_account: payee's account (účet příjemce); amount: amount (částka); currency: currency (měna); date: transaction date (datum transakce); reference: link to the invoice or financing (variable symbol, invoice number, message).",
      ),
    reasoning: s.string().describe("Why you chose this status: what is there, what is missing or unreadable, and where."),
  }),
  handler: async (ctx, input) =>
    recordRule(ctx, (run) => checkContents(PAYMENT_PROOF, run, getRequirements(ctx, run), getDocumentRead(ctx, run, input.document_id), input)),
});
