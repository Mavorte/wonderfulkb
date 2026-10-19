// Ranks the backoffice work queue: one row per case with a case-evaluator run.
// A case's status says whose move it is; its latest run and the client registry
// say how acute it is.

import { isCaseStatus, type CaseStatus } from "../cases/caseStatus.ts";
import { rawStatusLabel, ruleLabels } from "../review/ruleLabels.ts";

export type QueueIssue = { rule_id: string; status: string; expected: string | null; found: string | null; reasoning: string };

/** A case as the case-queue function returns it. */
export type QueueCase = {
  case_id: string;
  // False when the case API has no case with this id; client and dates are then empty.
  case_found: boolean;
  client_id: string | null;
  status: string;
  created_at: string | null;
  client: { name: string; ico: string; kyc_status: string | null } | null;
  evaluation: {
    evaluation_id: string;
    status: string;
    verdict: string | null;
    summary: string | null;
    started_at: string | null;
    finished_at: string | null;
    issues: QueueIssue[];
  };
};

// Blocking stops the case; material must be resolved before a decision.
export type Severity = "blocking" | "material";

export type Finding = { severity: Severity; title: string; detail: string; action: string };

// Listed most acute first; the queue renders tiers in this order.
// decision: the worker's move. waiting: the client's move. processing: the
// system's move. done: final.
export const tiers = ["decision", "waiting", "processing", "done"] as const;
export type Tier = (typeof tiers)[number];

export type TriagedCase = Omit<QueueCase, "status"> & { status: CaseStatus; tier: Tier; findings: Finding[] };

const tierByStatus: Record<CaseStatus, Tier> = {
  awaiting_decision: "decision",
  open: "waiting",
  awaiting_clarification: "waiting",
  intake_in_progress: "processing",
  evaluating: "processing",
  approved: "processing",
  completed: "done",
};

const issueSeverity: Record<string, Severity> = {
  conflict: "blocking",
  failed: "blocking",
  missing: "material",
  cannot_verify: "material",
};

const issueAction: Record<string, string> = {
  conflict: "Resolve the conflict between the documents",
  failed: "Check the failed rule in the case review",
  missing: "Request the missing item from the client",
  cannot_verify: "Verify it by hand in the case review",
};

// The case API does not move cases along the lifecycle yet and leaves them
// "open", so an open case is placed by its latest evaluator run. A failed run
// waits on the worker to run it again, so it counts as awaiting a decision.
export function statusOf(c: QueueCase): CaseStatus {
  if (c.status !== "open" && isCaseStatus(c.status)) return c.status;
  if (c.evaluation.status === "completed" || c.evaluation.status === "failed") return "awaiting_decision";
  return "evaluating";
}

export function findIssues(c: QueueCase): Finding[] {
  const findings: Finding[] = [];

  if (!c.case_found) {
    findings.push({
      severity: "blocking",
      title: "Case not in the case registry",
      detail: `The evaluator ran on case ${c.case_id}, which the case API does not know.`,
      action: "Check which case the evaluator was run on",
    });
  } else if (!c.client) {
    findings.push({
      severity: "blocking",
      title: "Client not in registry",
      detail: "The case points to a client that does not exist in the client registry.",
      action: "Link the case to a registered client",
    });
  } else if (c.client.kyc_status !== "ok") {
    findings.push({
      severity: "blocking",
      title: c.client.kyc_status ? `KYC ${c.client.kyc_status}` : "KYC not on file",
      detail: `${c.client.name} has no passed KYC check.`,
      action: "Run KYC before any further step",
    });
  }

  const evaluation = c.evaluation;
  if (evaluation.status === "failed") {
    findings.push({
      severity: "material",
      title: "Checks did not finish",
      detail: "The latest case-evaluator run failed, so no check results are available.",
      action: "Run the case evaluation again",
    });
  }

  if (evaluation.status === "completed") {
    for (const issue of evaluation.issues) {
      const label = ruleLabels[issue.rule_id] ?? issue.rule_id.replace(/_/g, " ");
      findings.push({
        severity: issueSeverity[issue.status] ?? "material",
        title: `${label}: ${(rawStatusLabel[issue.status] ?? issue.status).toLowerCase()}`,
        detail: issue.found ?? issue.reasoning,
        action: issueAction[issue.status] ?? "Check the rule in the case review",
      });
    }
  }

  // Blocking findings first, so the row leads with what stops the case.
  return findings.sort((a, b) => Number(b.severity === "blocking") - Number(a.severity === "blocking"));
}

const count = (c: TriagedCase, severity: Severity) => c.findings.filter((f) => f.severity === severity).length;

/** Most acute first: tier, then blocking and material findings, then the longest-waiting run. */
export function compareCases(a: TriagedCase, b: TriagedCase): number {
  return (
    tiers.indexOf(a.tier) - tiers.indexOf(b.tier) ||
    count(b, "blocking") - count(a, "blocking") ||
    count(b, "material") - count(a, "material") ||
    (a.evaluation.started_at ?? "").localeCompare(b.evaluation.started_at ?? "")
  );
}

export default function triage(cases: QueueCase[]): TriagedCase[] {
  return cases
    .map((c) => {
      const status = statusOf(c);
      const findings = status === "completed" ? [] : findIssues(c);
      return { ...c, status, tier: tierByStatus[status], findings };
    })
    .sort(compareCases);
}
