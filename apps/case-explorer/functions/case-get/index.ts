// Fetches one case (body: case_id).

import type { FunctionContext } from "@wonderful/types";
import { callAwsApi, getParam, missingParameter } from "../shared/upstream";

async function userFunction(context: FunctionContext) {
  const caseId = getParam(context, "case_id");
  if (!caseId) return missingParameter("case_id");
  return callAwsApi(context, `/cases/${encodeURIComponent(caseId)}`);
}
