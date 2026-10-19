import type { CaseStatus } from "./triage";

// Every case in the table is still "open", so these mock statuses show the later
// lifecycle steps on a few cases until the pipeline writes real ones.
const mockStatuses: Record<string, CaseStatus> = {
  "SYN-A03": "awaiting_clarification",
  "SYN-C09": "evaluating",
  "SYN-B04": "approved",
  "SYN-C01": "completed",
  "SYN-C03": "completed",
};

export default mockStatuses;
