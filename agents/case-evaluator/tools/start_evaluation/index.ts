import { s, w } from "@wonderful/types/schema";
import { isError, runFunction } from "../../lib/functions";
import { RULES } from "../../lib/rules";
import { type CaseMetadata, type Client, startRun } from "../../lib/run";

type CaseResult = {
  is_mock: boolean;
  case: { case_id: string; status: string; metadata?: CaseMetadata & Record<string, unknown> };
  client: Client | null;
};

type DocumentsResult = {
  documents: Array<{ document_id: string; title: string; label: string; processing_status: string; page_count: number }>;
};

export default w.tool({
  name: "start_evaluation",
  description:
    "Start evaluating a case. Loads the case, the client record from the bank's system and the list of uploaded documents (without their text), and opens an evaluation run that the evaluate_* tools write to. Each document has a short ref (D1, D2, ...): pass it wherever a tool asks for a document_id. Call this first.",
  params: s.object({
    case_id: s.string().describe("Case ID from the task payload, e.g. mock-solom-rec. Pass it exactly as given."),
  }),
  handler: async (ctx, { case_id }) => {
    const caseData = runFunction<CaseResult>(ctx, "eval-case-get", { case_id });
    if (isError(caseData)) return caseData;
    const list = runFunction<DocumentsResult>(ctx, "eval-documents-list", { case_id });
    if (isError(list)) return list;
    const run = await startRun(ctx, {
      case_id,
      is_mock: caseData.is_mock,
      client: caseData.client,
      case_metadata: {
        loan_number: caseData.case.metadata?.loan_number,
        asset: caseData.case.metadata?.asset,
        serial_number: caseData.case.metadata?.serial_number,
      },
      documents: list.documents.map(({ document_id, title, label }, i) => ({ document_id, ref: `D${i + 1}`, title, label })),
    });
    return {
      evaluation_id: run.evaluation_id,
      case_id,
      is_mock: caseData.is_mock,
      case: { status: caseData.case.status, metadata: caseData.case.metadata ?? {} },
      client: caseData.client,
      case_metadata: {
        loan_number: caseData.case.metadata?.loan_number,
        asset: caseData.case.metadata?.asset,
        serial_number: caseData.case.metadata?.serial_number,
      },
      // The agent sees only the refs: full document IDs made its tool calls long and slow to write.
      documents: list.documents.map(({ document_id: _, ...document }, i) => ({ ref: `D${i + 1}`, ...document })),
      rules_to_record: RULES,
    };
  },
});
