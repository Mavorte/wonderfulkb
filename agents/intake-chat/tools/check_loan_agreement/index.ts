import { s, w } from "@wonderful/types/schema";
import {
  DEFAULT_REQUIRED_DOCUMENTS,
  getErrorMessage,
  getNewFiles,
  getOutstanding,
  getState,
  isPdf,
  saveState,
  toRequiredDocuments,
} from "../../lib/intake";

const agreementSchema = s.object({
  document_kind: s.string().describe("What the document is, in a few Czech words, e.g. 'smlouva o úvěru' or 'faktura'."),
  is_loan_agreement: s.boolean().describe("Whether the document plausibly is a loan, credit, leasing or financing agreement."),
  contract_number: s.string().describe("The agreement's number, or an empty string."),
  required_documents: s
    .array(s.string())
    .describe("Documents the borrower must deliver before the loan is paid out, as short Czech names. Empty when the agreement lists none."),
});

const PROMPT = `The client uploaded this file as the loan agreement for their equipment financing (SG Equipment Finance / Komerční banka). The document is usually in Czech.

- is_loan_agreement: a deliberately loose check. Answer true if the document plausibly is a loan, credit, leasing or financing agreement (for example "Smlouva o úvěru", "Úvěrová smlouva", "Smlouva o financování"), even when it is a scan, unsigned, or some pages are missing. Answer false only if it clearly is something else, such as an invoice, an order, a protocol, a photo, an empty page or an unrelated document.
- contract_number: the agreement's number if it is shown, otherwise an empty string.
- required_documents: if the agreement lists the documents the borrower must deliver before the loan is paid out (for example under "Podmínky čerpání", "Odkládací podmínky" or "doklady předložené před čerpáním"), give each one as a short Czech name a client understands, such as "Daňový doklad (faktura) od dodavatele". Merge alternatives into one item, such as "Kupní smlouva nebo potvrzená objednávka". Leave out the agreement itself and its general terms (VOP). Return an empty list when the agreement has no such list.`;

export default w.tool({
  name: "check_loan_agreement",
  description:
    "Check the file the client just uploaded as their loan agreement. Reads it with OCR, checks loosely that it looks like a loan agreement, and reads the list of documents the agreement requires before disbursement (a default list is used when it has none). Call it whenever the client uploads a file before a loan agreement has been accepted.",
  params: s.object({}),
  handler: async (ctx) => {
    const state = getState(ctx);
    if (state.loan_agreement) {
      return {
        accepted: true,
        already_accepted: true,
        file: state.loan_agreement.name,
        outstanding: getOutstanding(state),
        next_step: "The loan agreement was already accepted. Call check_documents for files uploaded after it.",
      };
    }

    const newFiles = getNewFiles(state, await ctx.attachments.listFiles());
    const file = newFiles[newFiles.length - 1];
    if (!file) {
      return {
        accepted: false,
        problem: "no_new_file",
        next_step: "No new file has arrived. Ask the client to drag their loan agreement into the chat as a PDF.",
      };
    }

    if (!isPdf(file)) {
      state.checked[file.id] = { name: file.name, outcome: "rejected", document_kind: "není PDF" };
      saveState(ctx, state);
      return {
        accepted: false,
        file: file.name,
        problem: "not_a_pdf",
        next_step: "Ask the client to upload the loan agreement as a PDF file.",
      };
    }

    let result: { document_kind: string; is_loan_agreement: boolean; contract_number: string; required_documents: string[] };
    try {
      result = await ctx.ocr.extractTextFromAttachment(file.id, { structuredOutput: { schema: agreementSchema, prompt: PROMPT } });
    } catch (error) {
      console.log(`OCR of ${file.name} failed: ${getErrorMessage(error)}`);
      state.checked[file.id] = { name: file.name, outcome: "rejected", document_kind: "nečitelný soubor" };
      saveState(ctx, state);
      return {
        accepted: false,
        file: file.name,
        problem: "unreadable",
        next_step: "The file could not be read. Ask the client to upload the loan agreement again, ideally as a clearer PDF.",
      };
    }

    if (!result.is_loan_agreement) {
      state.checked[file.id] = { name: file.name, outcome: "rejected", document_kind: result.document_kind };
      saveState(ctx, state);
      return {
        accepted: false,
        file: file.name,
        document_kind: result.document_kind,
        next_step: "Tell the client this does not look like a loan agreement (say what it looks like) and ask them to upload their loan agreement.",
      };
    }

    const fromAgreement = toRequiredDocuments(result.required_documents);
    state.loan_agreement = { attachment_id: file.id, name: file.name, contract_number: result.contract_number || null };
    state.required_documents = fromAgreement.length > 0 ? fromAgreement : toRequiredDocuments(DEFAULT_REQUIRED_DOCUMENTS);
    state.required_documents_source = fromAgreement.length > 0 ? "agreement" : "default";
    state.checked[file.id] = { name: file.name, outcome: "loan_agreement", document_kind: result.document_kind };
    saveState(ctx, state);

    return {
      accepted: true,
      file: file.name,
      contract_number: state.loan_agreement.contract_number,
      required_documents: state.required_documents.map((doc) => doc.name),
      required_documents_source: state.required_documents_source,
      other_new_files: newFiles.length - 1,
      next_step:
        newFiles.length > 1
          ? "Confirm the loan agreement, then call check_documents for the other files the client already uploaded."
          : "Confirm the loan agreement and ask the client to upload all the required documents as PDF files. They can drop several at once.",
    };
  },
});
