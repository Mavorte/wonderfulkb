// Fetches one document (body: case_id, document_id, view). `view` picks the
// documents API endpoint: "validation" (default; text, label, description),
// "vectors" or "signatures".

import type { FunctionContext } from "@wonderful/types";
import { callAwsApi, getParam, missingParameter } from "../shared/upstream";

const VIEW_PATHS: Record<string, string> = {
  validation: "",
  vectors: "/vectors?include_values=false&similar_to_verified=3",
  signatures: "/signatures?match_client=true&include_vectors=false",
};

async function userFunction(context: FunctionContext) {
  const caseId = getParam(context, "case_id");
  const documentId = getParam(context, "document_id");
  if (!caseId) return missingParameter("case_id");
  if (!documentId) return missingParameter("document_id");
  const view = getParam(context, "view") || "validation";
  if (!(view in VIEW_PATHS)) return missingParameter("view (validation, vectors or signatures)");
  return callAwsApi(
    context,
    `/cases/${encodeURIComponent(caseId)}/documents/${encodeURIComponent(documentId)}${VIEW_PATHS[view]}`,
  );
}
