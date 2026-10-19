import { s, w } from "@wonderful/types/schema";
import { recordRule } from "../../lib/record";
import { checkContents } from "../../lib/rules/contents";
import { HANDOVER_PROTOCOL } from "../../lib/rules/contentSpecs";
import { getDocumentRead, getRequirements } from "../../lib/run";

export default w.tool({
  name: "evaluate_handover_protocol_contents",
  description:
    "Record rule handover_protocol_contents: whether the handover protocol or delivery note shows who hands over and who receives, the asset, date and condition, and is signed by both parties. Read the document with get_document first. The tool checks your status against the fields and the document's signatures, and rejects it if they disagree.",
  params: s.object({
    status: s.enum("passed", "missing", "cannot_verify", "not_applicable").describe(
      "passed if the handover protocol or delivery note (předávací protokol, dodací list) shows every mandatory field and signature; missing if any is absent or blank; cannot_verify if the document is too hard to read to tell (pages_failed or low confidence). If required_documents_present matched no document of type handover_protocol, send no document_id or fields and use: missing if a handover_protocol requirement has no document (required but not uploaded); cannot_verify if required_documents_present listed no requirements; not_applicable if the agreement doesn't require one.",
    ),
    document_id: s.optional(s.string()).describe("The handover protocol or delivery note (předávací protokol, dodací list) that required_documents_present matched. Leave out when no document was matched."),
    fields: s
      .optional(s.array(s.object({ field: s.enum("handed_over_by", "received_by", "asset", "handover_date", "condition"), value: s.optional(s.string()), page: s.optional(s.number()) })))
      .describe(
        "One entry per field, every field listed: field key, value as the document shows it (short), and its page. Leave out value (and page) when the document doesn't show the field. Leave out fields when no document was matched. Fields: handed_over_by: who hands over (předávající / dodavatel); received_by: who receives (přebírající / příjemce); asset: asset identification (předmět, výrobní číslo); handover_date: handover date (datum předání / převzetí); condition: condition or quantity (stav nebo množství). The tool checks the signatures itself, from what get_document returned: handing-over party (role supplier), receiving party (role borrower).",
      ),
    reasoning: s.string().describe("Why you chose this status: what is there, what is missing or unreadable, and where."),
  }),
  handler: async (ctx, input) =>
    recordRule(ctx, (run) => checkContents(HANDOVER_PROTOCOL, run, getRequirements(ctx, run), getDocumentRead(ctx, run, input.document_id), input)),
});
