// Case lifecycle, in order. Every case starts open and ends completed.
export const caseStatuses = [
  "open",
  "intake_in_progress",
  "evaluating",
  "awaiting_decision",
  "awaiting_clarification",
  "approved",
  "completed",
] as const;
export type CaseStatus = (typeof caseStatuses)[number];

export const caseStatusLabel: Record<CaseStatus, string> = {
  open: "Waiting for documents",
  intake_in_progress: "Intake in progress",
  evaluating: "Evaluating",
  awaiting_decision: "Awaiting decision",
  awaiting_clarification: "Awaiting clarification",
  approved: "Approved, writing",
  completed: "Completed",
};

export const isCaseStatus = (status: string): status is CaseStatus =>
  (caseStatuses as readonly string[]).includes(status);
