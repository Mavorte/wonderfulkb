import { s, w } from "@wonderful/types/schema";
import { recordRule } from "../../lib/record";
import { checkContents } from "../../lib/rules/contents";
import { INVOICE } from "../../lib/rules/contentSpecs";
import { getDocumentRead, getRequirements } from "../../lib/run";

export default w.tool({
  name: "evaluate_invoice_contents",
  description:
    "Record rule invoice_contents: whether the invoice / tax document required by the loan agreement shows its mandatory contents. Read the document with get_document first. The tool checks your status against the fields and the document's signatures, and rejects it if they disagree.",
  params: s.object({
    status: s.enum("passed", "missing", "cannot_verify", "not_applicable").describe(
      "passed if the invoice / tax document (faktura, daňový doklad) shows every mandatory field and signature; missing if any is absent or blank; cannot_verify if the document is too hard to read to tell (pages_failed or low confidence). If required_documents_present matched no document of type invoice, send no document_id or fields and use: missing if a invoice requirement has no document (required but not uploaded); cannot_verify if required_documents_present listed no requirements; not_applicable if the agreement doesn't require one.",
    ),
    document_id: s.optional(s.string()).describe("The invoice / tax document (faktura, daňový doklad) that required_documents_present matched. Leave out when no document was matched."),
    fields: s
      .optional(s.array(s.object({ field: s.enum("issuer", "customer", "number", "subject", "price", "vat", "issue_date", "supply_date", "due_date", "payment_details"), value: s.optional(s.string()), page: s.optional(s.number()) })))
      .describe(
        "One entry per field, every field listed: field key, value as the document shows it (short), and its page. Leave out value (and page) when the document doesn't show the field. Leave out fields when no document was matched. Fields: issuer: issuer identity (vystavitel / dodavatel: name, IČO, address); customer: customer identity (odběratel / příjemce: name, IČO, address); number: document number (číslo dokladu); subject: subject of supply (předmět plnění); price: price (cena); vat: VAT (DPH), or why none is charged; issue_date: issue date (datum vystavení); supply_date: date of taxable supply (DUZP) (optional); due_date: due date (splatnost); payment_details: payment details (bank account, variable symbol) (optional).",
      ),
    reasoning: s.string().describe("Why you chose this status: what is there, what is missing or unreadable, and where."),
  }),
  handler: async (ctx, input) =>
    recordRule(ctx, (run) => checkContents(INVOICE, run, getRequirements(ctx, run), getDocumentRead(ctx, run, input.document_id), input)),
});
