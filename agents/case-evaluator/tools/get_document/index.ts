import { s, w } from "@wonderful/types/schema";
import { isError, runFunction } from "../../lib/functions";
import { NO_RUN } from "../../lib/record";
import { type EvalRegion, compactRegions } from "../../lib/regions";
import { type Run, type RunContext, findDocument, getRun, saveDocumentRead, saveDocumentRegions } from "../../lib/run";

type DocumentResult = {
  document_id: string;
  title: string;
  label: string;
  confidence: number | null;
  pages_failed: number[];
  pages: Array<{ page: number; text: string }>;
};

type SignaturesResult = {
  signatures: Array<{ page: number; role: string; evidence: string }>;
};

type RegionsResult = { status: string; regions: EvalRegion[] };

export default w.tool({
  name: "get_document",
  description:
    "Read one document of the case being evaluated: its extracted text, split into numbered pages, and the signatures detected in it (role, page, and the text next to each). A page with empty text is blank, unless it is listed in pages_failed (could not be read). Read only the documents a rule needs, one at a time.",
  params: s.object({
    document_id: s.string().describe("The document's ref from the start_evaluation document list, e.g. D3."),
  }),
  handler: async (ctx, { document_id }) => {
    const run = getRun(ctx);
    if (!run) return NO_RUN;
    const known = findDocument(run, document_id);
    const id = known?.document_id ?? document_id.trim();
    const document = runFunction<DocumentResult>(ctx, "eval-document-get", { case_id: run.case_id, document_id: id });
    if (isError(document)) return document;
    const found = runFunction<SignaturesResult>(ctx, "eval-document-signatures", { case_id: run.case_id, document_id: id });
    const signatures = isError(found) ? null : found.signatures.map(({ role, page, evidence }) => ({ role, page, evidence }));
    const { title, label, confidence, pages_failed, pages } = document;
    saveDocumentRead(ctx, run, id, {
      page_count: pages.length,
      empty_pages: pages.filter((p) => !p.text).map((p) => p.page),
      pages_failed,
      confidence,
      signatures: signatures && signatures.map(({ role, page }) => ({ role, page })),
    });
    loadRegions(ctx, run, id);
    return {
      ref: known?.ref ?? id, title, label, confidence, pages_failed, pages,
      signatures,
      ...(isError(found) && { signatures_error: `${found.error}${found.message ? `: ${found.message}` : ""}` }),
    };
  },
});

// Keeps the document's regions for placing the evaluate_* sources (lib/regions.ts).
// The agent doesn't see them, and without them sources stay at page level.
function loadRegions(ctx: Parameters<typeof runFunction>[0] & RunContext, run: Run, documentId: string) {
  try {
    const result = runFunction<RegionsResult>(ctx, "eval-document-regions", { case_id: run.case_id, document_id: documentId });
    if (isError(result) || result.status !== "completed" || !Array.isArray(result.regions) || !result.regions.length) return;
    saveDocumentRegions(ctx, run, documentId, compactRegions(result.regions));
  } catch (error) {
    console.log(`regions of ${documentId} not loaded: ${error}`);
  }
}
