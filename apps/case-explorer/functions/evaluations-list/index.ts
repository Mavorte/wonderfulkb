// Lists a case's evaluator runs and their per-rule results (body: case_id).

import type { FunctionContext } from "@wonderful/types";
import { EVALUATIONS_TABLE, RESULTS_TABLE, listCaseRows, tableResult } from "../shared/evaluations";
import { getParam, missingParameter } from "../shared/upstream";

async function userFunction(context: FunctionContext) {
  const caseId = getParam(context, "case_id");
  if (!caseId) return missingParameter("case_id");
  return tableResult(async () => {
    const [evaluations, results] = await Promise.all([
      listCaseRows(context, EVALUATIONS_TABLE, caseId, [{ column: "started_at", direction: "desc" }]),
      listCaseRows(context, RESULTS_TABLE, caseId, [
        { column: "evaluation_id", direction: "asc" },
        { column: "rule_id", direction: "asc" },
      ]),
    ]);
    return {
      case_id: caseId,
      evaluations: evaluations.map((row) => row.data),
      results: results.map((row) => row.data),
    };
  });
}
