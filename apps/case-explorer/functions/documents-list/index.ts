// Lists a case's documents (body: case_id, optional next_token).

import type { FunctionContext } from "@wonderful/types";
import { callAwsApi, getParam, getQuery, missingParameter } from "../shared/upstream";

async function userFunction(context: FunctionContext) {
  const caseId = getParam(context, "case_id");
  if (!caseId) return missingParameter("case_id");
  const query = getQuery({ next_token: getParam(context, "next_token") });
  return callAwsApi(context, `/cases/${encodeURIComponent(caseId)}/documents${query}`);
}
