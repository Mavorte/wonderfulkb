// Returns one case-evaluator run (body: evaluation_id, else the latest run of
// case_id, else the latest run overall) with its per-rule results, or
// `evaluation: null` when there is none.
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
  // A case still waiting for documents has no run yet; that is not an error.
  const evaluation = latest.rows[0]?.data;
  if (!evaluation) return { evaluation: null, results: [] };

  // Unordered: pending rows have no recorded_at, so the app sorts them by its checklist.
  const results = await context.tables.filter(
    RESULTS_TABLE,
    [{ column: "evaluation_id", operator: "eq", value: String(evaluation.evaluation_id) }],
    RESULTS_LIMIT,
    0,
  );

  return { evaluation, results: results.rows.map((row) => row.data) };
}
