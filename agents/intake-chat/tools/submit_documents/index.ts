import { s, w } from "@wonderful/types/schema";
import { getErrorMessage, getOutstanding, getState, saveState } from "../../lib/intake";
import { resolveCase, sendToIngest } from "../../lib/ingest";

export default w.tool({
  name: "submit_documents",
  description:
    "Send the loan agreement and every accepted document to KB for the client's case. Call it once check_documents reports that all required documents have arrived.",
  params: s.object({}),
  handler: async (ctx) => {
    const state = getState(ctx);
    if (state.submitted) {
      return { submitted: true, already_submitted: true, document_count: state.submitted.document_count };
    }
    if (!state.loan_agreement) {
      return { submitted: false, problem: "no_loan_agreement", next_step: "Ask the client for their loan agreement first." };
    }
    const outstanding = getOutstanding(state);
    if (outstanding.length > 0) {
      return { submitted: false, problem: "documents_missing", outstanding, next_step: "Ask the client for the outstanding documents." };
    }

    const intakeCase = resolveCase(ctx);
    if ("error" in intakeCase) {
      return {
        submitted: false,
        problem: intakeCase.error,
        message: intakeCase.message,
        next_step: "Tell the client the documents could not be sent and ask them to open the link from their KB message again.",
      };
    }

    const ids = [...new Set([state.loan_agreement.attachment_id, ...state.required_documents.flatMap((doc) => doc.attachment_ids)])];
    try {
      const files = await Promise.all(
        ids.map(async (id) => ({ name: state.checked[id]?.name ?? `${id}.pdf`, data: await ctx.attachments.getFile(id) })),
      );
      const result = await sendToIngest(ctx, intakeCase, files);
      if ("error" in result) {
        console.log(`submit failed: ${result.message}`);
        return {
          submitted: false,
          problem: result.error,
          next_step: "Tell the client the documents could not be sent right now. Offer to try again with submit_documents.",
        };
      }
      state.submitted = { case_id: intakeCase.case_id, document_count: files.length };
      saveState(ctx, state);
      return {
        submitted: true,
        document_count: files.length,
        next_step: "Thank the client: KB has received all their documents and will be in touch.",
      };
    } catch (error) {
      console.log(`submit failed: ${getErrorMessage(error)}`);
      return {
        submitted: false,
        problem: "upstream",
        next_step: "Tell the client the documents could not be sent right now. Offer to try again with submit_documents.",
      };
    }
  },
});
