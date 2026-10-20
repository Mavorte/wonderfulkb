import type { AwsCase } from "../lib/awsApi";
import type { AwsClient } from "../client-directory/directory";

/** Row of agent_functions.case_evaluations. */
export type EvaluationRow = {
  evaluation_id: string;
  case_id: string;
  status: string;
  verdict?: string | null;
  summary?: string | null;
  is_mock?: boolean | null;
  started_at?: string | null;
  finished_at?: string | null;
};

/** Row of agent_functions.case_evaluation_results. */
export type ResultRow = {
  evaluation_id: string;
  rule_id: string;
  status: string;
  expected?: string | null;
  found?: string | null;
  reasoning: string;
};

export type QueueIssue = { rule_id: string; status: string; expected: string | null; found: string | null; reasoning: string };

export type QueueEvaluation = {
  evaluation_id: string;
  status: string;
  verdict: string | null;
  summary: string | null;
  started_at: string | null;
  finished_at: string | null;
  issues: QueueIssue[];
};

export type QueueCase = {
  case_id: string;
  // False when the case API has no case with this id; client and dates are then empty.
  case_found: boolean;
  client_id: string | null;
  status: string;
  created_at: string | null;
  client: { name: string; ico: string; kyc_status: string | null } | null;
  // Null until the case-evaluator has run on the case.
  evaluation: QueueEvaluation | null;
};

// Not issues; pending rules are not recorded yet.
const CLEAN_RESULTS = new Set(["passed", "not_applicable", "pending"]);

/** The newest evaluator run per case; mock runs are test data and never count. */
export function latestEvaluations(evaluations: EvaluationRow[]): Map<string, EvaluationRow> {
  const latest = new Map<string, EvaluationRow>();
  for (const evaluation of evaluations) {
    if (evaluation.is_mock) continue;
    const current = latest.get(evaluation.case_id);
    if (!current || (evaluation.started_at ?? "") > (current.started_at ?? "")) latest.set(evaluation.case_id, evaluation);
  }
  return latest;
}

function toQueueEvaluation(evaluation: EvaluationRow, results: ResultRow[]): QueueEvaluation {
  return {
    evaluation_id: evaluation.evaluation_id,
    status: evaluation.status,
    verdict: evaluation.verdict ?? null,
    summary: evaluation.summary ?? null,
    started_at: evaluation.started_at ?? null,
    finished_at: evaluation.finished_at ?? null,
    issues: results
      .filter((r) => r.evaluation_id === evaluation.evaluation_id && !CLEAN_RESULTS.has(r.status))
      .map((r) => ({
        rule_id: r.rule_id,
        status: r.status,
        expected: r.expected ?? null,
        found: r.found ?? null,
        reasoning: r.reasoning,
      })),
  };
}

/**
 * One queue row per case: every case of the case API, then every evaluated case
 * the case API does not know. Each row carries its client and its latest run
 * with the rules that did not pass.
 */
export function createQueue(
  cases: AwsCase[],
  latest: Map<string, EvaluationRow>,
  results: ResultRow[],
  clients: AwsClient[],
): QueueCase[] {
  const clientsById = new Map(clients.map((c) => [c.client_id, c]));
  const known = new Set(cases.map((c) => c.case_id));
  const evaluationOf = (caseId: string) => {
    const evaluation = latest.get(caseId);
    return evaluation ? toQueueEvaluation(evaluation, results) : null;
  };
  const listed = cases.map((awsCase): QueueCase => {
    const client = clientsById.get(awsCase.client_id);
    return {
      case_id: awsCase.case_id,
      case_found: true,
      client_id: awsCase.client_id,
      status: awsCase.status,
      created_at: awsCase.created_at,
      client: client ? { name: client.name, ico: client.ico, kyc_status: client.kyc?.status ?? null } : null,
      evaluation: evaluationOf(awsCase.case_id),
    };
  });
  const unknown = [...latest.keys()]
    .filter((caseId) => !known.has(caseId))
    .map((caseId): QueueCase => ({
      case_id: caseId,
      case_found: false,
      client_id: null,
      status: "open",
      created_at: null,
      client: null,
      evaluation: evaluationOf(caseId),
    }));
  return [...listed, ...unknown];
}
