// Deletes every evaluator run and result row of every case (no body).
// Results go first, so a failure halfway never leaves results without their run.

import type { FunctionContext } from "@wonderful/types";
import { EVALUATIONS_TABLE, RESULTS_TABLE, deleteCaseRows, tableResult } from "../shared/evaluations";

async function userFunction(context: FunctionContext) {
  return tableResult(async () => {
    const results = await deleteCaseRows(context, RESULTS_TABLE);
    const evaluations = await deleteCaseRows(context, EVALUATIONS_TABLE);
    return { deleted: { evaluations, results } };
  });
}
