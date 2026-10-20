// Returns one evaluator run and its per-rule results (body: evaluation_id).
// The app polls it while a run is selected.

import type { FunctionContext } from "@wonderful/types";
import { EVALUATIONS_TABLE, RESULTS_TABLE, listRowsBy, tableResult } from "../shared/evaluations";
import { getParam, missingParameter } from "../shared/upstream";

async function userFunction(context: FunctionContext) {
  const evaluationId = getParam(context, "evaluation_id");
  if (!evaluationId) return missingParameter("evaluation_id");
  return tableResult(async () => {
    const [evaluations, results] = await Promise.all([
      listRowsBy(context, EVALUATIONS_TABLE, "evaluation_id", evaluationId, []),
      listRowsBy(context, RESULTS_TABLE, "evaluation_id", evaluationId, [{ column: "rule_id", direction: "asc" }]),
    ]);
    return {
      evaluation_id: evaluationId,
      evaluation: evaluations[0]?.data ?? null,
      results: results.map((row) => row.data),
    };
  });
}
