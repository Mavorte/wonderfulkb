// Lists the Work queue: one row per case of the AWS case/client API (GET /cases)
// with its client (GET /clients) and, from the agent-functions tables linked to
// this app, its latest case-evaluator run and the rules that run did not pass.

import type { FunctionContext } from "@wonderful/types";
import type { AwsClient } from "../client-directory/directory";
import { getErrorMessage, listAll, requestAwsApi, type AwsCase } from "../lib/awsApi";
import { createQueue, latestEvaluations, type EvaluationRow, type QueueCase, type ResultRow } from "./queue";

const EVALUATIONS_TABLE = "agent_functions.case_evaluations";
const RESULTS_TABLE = "agent_functions.case_evaluation_results";
const EVALUATIONS_LIMIT = 500;
const RESULTS_LIMIT = 100;
const CONCURRENCY = 4;
// Case ids come from another app's table, so only well-formed ones reach the case API.
const CASE_ID_PATTERN = /^[A-Za-z0-9_-][A-Za-z0-9._-]{0,127}$/;

type CaseQueueResponse = { cases: QueueCase[]; truncated: boolean } | { error: "evaluations" | "upstream" };

/** Runs `task` over `items`, at most CONCURRENCY at a time. */
async function forEachLimited<T>(items: T[], task: (item: T) => Promise<void>) {
  const queue = [...items];
  await Promise.all(
    Array.from({ length: CONCURRENCY }, async () => {
      for (let item = queue.shift(); item !== undefined; item = queue.shift()) await task(item);
    }),
  );
}

async function readEvaluations(context: FunctionContext) {
  const rows = await context.tables.filter(EVALUATIONS_TABLE, [], EVALUATIONS_LIMIT, 0, [
    { column: "started_at", direction: "desc" },
  ]);
  // A full page means older runs were left out, so some cases may be missing.
  const truncated = rows.rows.length >= EVALUATIONS_LIMIT;
  const latest = latestEvaluations(rows.rows.map((row) => row.data as EvaluationRow));
  const results: ResultRow[] = [];
  await forEachLimited([...latest.values()], async (evaluation) => {
    const page = await context.tables.filter(
      RESULTS_TABLE,
      [{ column: "evaluation_id", operator: "eq", value: evaluation.evaluation_id }],
      RESULTS_LIMIT,
      0,
    );
    results.push(...page.rows.map((row) => row.data as ResultRow));
  });
  return { latest, results, truncated };
}

/** Every case of the case API, plus the evaluated cases a truncated list left out. */
async function readCases(context: FunctionContext, evaluatedIds: string[]) {
  const page = await listAll<AwsCase>(context, "/cases", "cases");
  if (!page.truncated) return page;
  const listed = new Set(page.items.map((c) => c.case_id));
  const unlisted = evaluatedIds.filter((id) => !listed.has(id) && CASE_ID_PATTERN.test(id));
  await forEachLimited(unlisted, async (caseId) => {
    const response = await requestAwsApi<AwsCase>(context, `/cases/${encodeURIComponent(caseId)}`);
    if (response.ok && response.body) page.items.push(response.body);
    else if (response.status !== 404) throw new Error(`/cases/${caseId} returned ${response.status}`);
  });
  return page;
}

async function userFunction(context: FunctionContext): Promise<CaseQueueResponse> {
  let evaluations;
  try {
    evaluations = await readEvaluations(context);
  } catch (error) {
    console.log(`case evaluations could not be read: ${getErrorMessage(error)}`);
    context.response.setStatus(502);
    return { error: "evaluations" };
  }

  try {
    const [cases, clients] = await Promise.all([
      readCases(context, [...evaluations.latest.keys()]),
      listAll<AwsClient>(context, "/clients", "clients"),
    ]);
    return {
      cases: createQueue(cases.items, evaluations.latest, evaluations.results, clients.items),
      truncated: evaluations.truncated || cases.truncated || clients.truncated,
    };
  } catch (error) {
    console.log(`case queue request failed: ${getErrorMessage(error)}`);
  }
  context.response.setStatus(502);
  return { error: "upstream" };
}
