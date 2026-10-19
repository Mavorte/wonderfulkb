// Deletes every evaluator run and result row of a case (body: case_id).
// Results go first, so a failure halfway never leaves results without their run.

import type { FunctionContext } from "@wonderful/types";
import { EVALUATIONS_TABLE, RESULTS_TABLE, deleteCaseRows, tableResult } from "../shared/evaluations";
import { getParam, missingParameter } from "../shared/upstream";

async function userFunction(context: FunctionContext) {
  const caseId = getParam(context, "case_id");
  if (!caseId) return missingParameter("case_id");
  return tableResult(async () => {
    const results = await deleteCaseRows(context, RESULTS_TABLE, caseId);
    const evaluations = await deleteCaseRows(context, EVALUATIONS_TABLE, caseId);
    return { case_id: caseId, deleted: { evaluations, results } };
  });
}
