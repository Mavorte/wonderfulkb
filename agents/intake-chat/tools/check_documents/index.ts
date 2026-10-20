import type { Context } from "@wonderful/types";
import { s, w } from "@wonderful/types/schema";
import {
  type CheckedFile,
  type FileInfo,
  type IntakeState,
  getErrorMessage,
  getNewFiles,
  getOutstanding,
  getState,
  isPdf,
  saveState,
} from "../../lib/intake";

function getPrompt(state: IntakeState): string {
  const list = state.required_documents.map((doc) => `- ${doc.key}: ${doc.name}`).join("\n");
  return `The client is uploading the documents their loan agreement requires before the loan is paid out. The required documents are:
${list}

Decide which of them this file is. This is a deliberately loose check: pick a requirement when the file plausibly is that kind of document. Do not check names, amounts, dates or signatures. Answer "loan_agreement" when the file is the loan agreement itself again, and "none" only when it clearly is none of them, such as a photo, an empty page or an unrelated document.
- document_kind: what the file is, in a few Czech words.
- reason: one short sentence.`;
}

async function checkFile(ctx: Context, state: IntakeState, file: FileInfo): Promise<CheckedFile> {
  if (!isPdf(file)) return { name: file.name, outcome: "rejected", document_kind: "není PDF" };
  const schema = s.object({
    document_kind: s.string(),
    requirement: s.enum(...state.required_documents.map((doc) => doc.key), "loan_agreement", "none"),
    reason: s.string(),
  });
  try {
    const result = await ctx.ocr.extractTextFromAttachment(file.id, { structuredOutput: { schema, prompt: getPrompt(state) } });
    const requirement = state.required_documents.find((doc) => doc.key === result.requirement);
    return requirement
      ? { name: file.name, outcome: "accepted", document_kind: result.document_kind, requirement: requirement.key }
      : { name: file.name, outcome: "rejected", document_kind: result.document_kind };
  } catch (error) {
    console.log(`OCR of ${file.name} failed: ${getErrorMessage(error)}`);
    return { name: file.name, outcome: "rejected", document_kind: "nečitelný soubor" };
  }
}

export default w.tool({
  name: "check_documents",
  description:
    "Check the files the client uploaded after the loan agreement. Reads each new file with OCR and checks loosely which required document it is. Returns what was accepted, what is still outstanding, and whether everything has arrived. Call it whenever the client uploads files after the loan agreement was accepted.",
  params: s.object({}),
  handler: async (ctx) => {
    const state = getState(ctx);
    if (!state.loan_agreement) {
      return { problem: "no_loan_agreement", next_step: "No loan agreement has been accepted yet. Call check_loan_agreement instead." };
    }

    const newFiles = getNewFiles(state, await ctx.attachments.listFiles());
    if (newFiles.length === 0) {
      return {
        problem: "no_new_file",
        outstanding: getOutstanding(state),
        next_step: "No new file has arrived. Ask the client to drag the outstanding documents into the chat as PDF files.",
      };
    }

    const checked = await Promise.all(newFiles.map((file) => checkFile(ctx, state, file)));
    newFiles.forEach((file, index) => {
      const result = checked[index];
      state.checked[file.id] = result;
      const requirement = state.required_documents.find((doc) => doc.key === result.requirement);
      requirement?.attachment_ids.push(file.id);
    });
    saveState(ctx, state);

    const outstanding = getOutstanding(state);
    return {
      files: checked.map(({ name, outcome, document_kind, requirement }) => ({
        file: name,
        accepted: outcome === "accepted",
        looks_like: document_kind,
        counts_as: state.required_documents.find((doc) => doc.key === requirement)?.name ?? null,
      })),
      outstanding,
      all_received: outstanding.length === 0,
      next_step:
        outstanding.length === 0
          ? "All required documents have arrived. Call submit_documents now."
          : "Tell the client which files were accepted and which were not (and why), then ask for the outstanding documents.",
    };
  },
});
