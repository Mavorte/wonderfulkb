// Returns one case-evaluator run (body: evaluation_id, else the latest run of
// case_id, else the latest run overall) with its per-rule results.
// Both tables are owned by the agent-functions app and linked to this one.

import type { FunctionContext } from "@wonderful/types";

const EVALUATIONS_TABLE = "agent_functions.case_evaluations";
const RESULTS_TABLE = "agent_functions.case_evaluation_results";
const RESULTS_LIMIT = 100;

export async function userFunction(context: FunctionContext) {
  const requested = String(context.data?.evaluation_id ?? "").trim();
  const caseId = String(context.data?.case_id ?? "").trim();

  const latest = await context.tables.filter(
    EVALUATIONS_TABLE,
    requested
      ? [{ column: "evaluation_id", operator: "eq", value: requested }]
      : caseId
        ? [{ column: "case_id", operator: "eq", value: caseId }]
        : [],
    1,
    0,
    [{ column: "started_at", direction: "desc" }],
  );
  const evaluation = latest.rows[0]?.data;
  if (!evaluation) {
    context.response.setStatus(404);
    return { error: "evaluation_not_found" };
  }

  const results = await context.tables.filter(
    RESULTS_TABLE,
    [{ column: "evaluation_id", operator: "eq", value: String(evaluation.evaluation_id) }],
    RESULTS_LIMIT,
    0,
    [{ column: "recorded_at", direction: "asc" }],
  );

  return { evaluation, results: results.rows.map((row) => row.data) };
}
