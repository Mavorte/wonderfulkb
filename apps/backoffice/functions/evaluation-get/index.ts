// Returns one case-evaluator run (body: evaluation_id; latest run when omitted),
// its per-rule results, and the most recent runs so the review screen can switch.
// Both tables are owned by the agent-functions app and linked to this one.

import type { FunctionContext } from "@wonderful/types";

const EVALUATIONS_TABLE = "agent_functions.case_evaluations";
const RESULTS_TABLE = "agent_functions.case_evaluation_results";
const RECENT_LIMIT = 50;
const RESULTS_LIMIT = 100;

async function userFunction(context: FunctionContext) {
  const requested = String(context.data?.evaluation_id ?? "").trim();

  const recent = await context.tables.filter(EVALUATIONS_TABLE, [], RECENT_LIMIT, 0, [
    { column: "started_at", direction: "desc" },
  ]);
  const evaluations = recent.rows.map((row) => row.data);

  let evaluation = requested ? evaluations.find((e) => e.evaluation_id === requested) : evaluations[0];
  if (requested && !evaluation) {
    const byId = await context.tables.filter(
      EVALUATIONS_TABLE,
      [{ column: "evaluation_id", operator: "eq", value: requested }],
      1,
      0,
    );
    evaluation = byId.rows[0]?.data;
  }
  if (!evaluation) {
    context.response.setStatus(404);
    return { error: "evaluation_not_found", evaluations };
  }

  const results = await context.tables.filter(
    RESULTS_TABLE,
    [{ column: "evaluation_id", operator: "eq", value: String(evaluation.evaluation_id) }],
    RESULTS_LIMIT,
    0,
    [{ column: "recorded_at", direction: "asc" }],
  );

  return { evaluation, results: results.rows.map((row) => row.data), evaluations };
}
