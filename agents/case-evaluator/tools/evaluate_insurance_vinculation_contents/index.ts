import { s, w } from "@wonderful/types/schema";
import { recordRule } from "../../lib/record";
import { checkContents } from "../../lib/rules/contents";
import { INSURANCE_VINCULATION } from "../../lib/rules/contentSpecs";
import { getDocumentRead, getRequirements } from "../../lib/run";

export default w.tool({
  name: "evaluate_insurance_vinculation_contents",
  description:
    "Record rule insurance_vinculation_contents: whether the insurance vinculation shows policyholder, insurer, SGEF as beneficiary, the asset, policy number, amount and the insurer's date and signature. Read the document with get_document first. The tool checks your status against the fields and the document's signatures, and rejects it if they disagree.",
  params: s.object({
    status: s.enum("passed", "missing", "cannot_verify", "not_applicable").describe(
      "passed if the insurance vinculation (prohlášení o vinkulaci pojištění) shows every mandatory field and signature; missing if any is absent or blank; cannot_verify if the document is too hard to read to tell (pages_failed or low confidence). If required_documents_present matched no document of type insurance_vinculation, send no document_id or fields and use: missing if a insurance_vinculation requirement has no document (required but not uploaded); cannot_verify if required_documents_present listed no requirements; not_applicable if the agreement doesn't require one.",
    ),
    document_id: s.optional(s.string()).describe("The insurance vinculation (prohlášení o vinkulaci pojištění) that required_documents_present matched. Leave out when no document was matched."),
    fields: s
      .optional(s.array(s.object({ field: s.enum("policyholder", "insurer", "beneficiary", "insured_asset", "policy_number", "insured_amount", "benefit_clause", "insurer_date"), value: s.optional(s.string()), page: s.optional(s.number()) })))
      .describe(
        "One entry per field, every field listed: field key, value as the document shows it (short), and its page. Leave out value (and page) when the document doesn't show the field. Leave out fields when no document was matched. Fields: policyholder: policyholder (pojistník); insurer: insurer (pojistitel); beneficiary: SGEF as beneficiary (poskytovatel financování); insured_asset: insured asset (předmět pojištění); policy_number: policy number (číslo pojistné smlouvy); insured_amount: scope or amount insured (rozsah, pojistná částka); benefit_clause: commitment that benefits are paid to SGEF; insurer_date: insurer's date. The tool checks the signatures itself, from what get_document returned: insurer (role insurer).",
      ),
    reasoning: s.string().describe("Why you chose this status: what is there, what is missing or unreadable, and where."),
  }),
  handler: async (ctx, input) =>
    recordRule(ctx, (run) => checkContents(INSURANCE_VINCULATION, run, getRequirements(ctx, run), getDocumentRead(ctx, run, input.document_id), input)),
});
