// Starts the case-evaluator agent for a case (body: case_id). The webhook only
// passes on what is inside `payload`, so the case ID goes there.

import type { FunctionContext } from "@wonderful/types";
import {
  EVALUATOR_WEBHOOK_SECRET,
  EVALUATOR_WEBHOOK_URL,
  callUpstream,
  getParam,
  missingParameter,
} from "../shared/upstream";

async function userFunction(context: FunctionContext) {
  const caseId = getParam(context, "case_id");
  if (!caseId) return missingParameter("case_id");
  return callUpstream(EVALUATOR_WEBHOOK_URL, EVALUATOR_WEBHOOK_SECRET, {
    method: "POST",
    body: { payload: { case_id: caseId } },
  });
}
