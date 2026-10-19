import { s, w } from "@wonderful/types/schema";
import { recordRule } from "../../lib/record";
import { checkContents } from "../../lib/rules/contents";
import { TECHNICAL_SPECIFICATION } from "../../lib/rules/contentSpecs";
import { getDocumentRead, getRequirements } from "../../lib/run";

export default w.tool({
  name: "evaluate_technical_specification_contents",
  description:
    "Record rule technical_specification_contents: whether the technical specification identifies the product, model, manufacturer, parameters and serial number. Read the document with get_document first. The tool checks your status against the fields and the document's signatures, and rejects it if they disagree.",
  params: s.object({
    status: s.enum("passed", "missing", "cannot_verify", "not_applicable").describe(
      "passed if the technical specification (technická specifikace) shows every mandatory field and signature; missing if any is absent or blank; cannot_verify if the document is too hard to read to tell (pages_failed or low confidence). If required_documents_present matched no document of type technical_specification, send no document_id or fields and use: missing if a technical_specification requirement has no document (required but not uploaded); cannot_verify if required_documents_present listed no requirements; not_applicable if the agreement doesn't require one.",
    ),
    document_id: s.optional(s.string()).describe("The technical specification (technická specifikace) that required_documents_present matched. Leave out when no document was matched."),
    fields: s
      .optional(s.array(s.object({ field: s.enum("product", "model", "manufacturer", "parameters", "serial_number"), value: s.optional(s.string()), page: s.optional(s.number()) })))
      .describe(
        "One entry per field, every field listed: field key, value as the document shows it (short), and its page. Leave out value (and page) when the document doesn't show the field. Leave out fields when no document was matched. Fields: product: product identification (předmět); model: model / type; manufacturer: manufacturer (výrobce); parameters: technical parameters; serial_number: serial number / VIN (optional).",
      ),
    reasoning: s.string().describe("Why you chose this status: what is there, what is missing or unreadable, and where."),
  }),
  handler: async (ctx, input) =>
    recordRule(ctx, (run) => checkContents(TECHNICAL_SPECIFICATION, run, getRequirements(ctx, run), getDocumentRead(ctx, run, input.document_id), input)),
});
