// Ranks cases for the backoffice work queue. A case's status says whose move it
// is; findings derived from the client registry, the uploaded documents and the
// loan terms extracted into case metadata say how acute it is.

import type { CaseStatus } from "../cases/caseStatus";

export type { CaseStatus };

export type QueueCase = {
  case_id: string;
  client_id: string;
  status: CaseStatus;
  created_at: string;
  client: { name: string; ico: string; kyc_status: string | null; kyc_checked_at: string | null } | null;
  principal: number | null;
  months: number | null;
  schedule_rows: number;
  disbursement: string | null;
  dates: Partial<Record<string, string>>;
  expected_documents: string[];
  documents: { filename: string; received_at: string; label?: string; confidence?: number }[];
};

// Blocking stops the case; material must be resolved before a decision.
export type Severity = "blocking" | "material";

export type Finding = { severity: Severity; title: string; detail: string; action: string };

// Listed most acute first; the queue renders tiers in this order.
// decision: the worker's move. waiting: the client's move. processing: the
// system's move. done: final.
export const tiers = ["decision", "waiting", "processing", "done"] as const;
export type Tier = (typeof tiers)[number];

export type TriagedCase = QueueCase & { tier: Tier; findings: Finding[] };

const documentNames: Record<string, string> = {
  uver: "loan agreement",
  faktura: "invoice",
  predani: "handover protocol",
  cerpani: "drawdown request",
  objednavka: "purchase order",
  vinkulace: "insurance assignment",
  zajisteni: "security transfer",
  uhrada: "payment confirmation",
  splatky: "repayment schedule",
  nabidka: "offer",
  ruceni: "guarantee",
  specifikace: "technical specification",
  dodaci_list: "delivery note",
  pojisteni: "insurance policy",
};

export const documentName = (key: string) => documentNames[key] ?? key;

export function findIssues(c: QueueCase): Finding[] {
  const findings: Finding[] = [];
  const { dates } = c;

  if (!c.client) {
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

  // Paying the supplier directly before the contract is signed means money left without a binding loan.
  const paidOn = dates.payment ?? dates.first_tranche;
  if (c.disbursement === "supplier_direct" && paidOn && dates.signing && paidOn < dates.signing) {
    findings.push({
      severity: "blocking",
      title: "Paid out before signing",
      detail: `Supplier paid on ${paidOn}, contract signed on ${dates.signing}.`,
      action: "Hold the case and verify the signing date on the contract",
    });
  }

  if (dates.buyer_payment && dates.first_tranche && dates.first_tranche < dates.buyer_payment) {
    findings.push({
      severity: "blocking",
      title: "Drawn before own contribution",
      detail: `First tranche on ${dates.first_tranche}, client's own payment on ${dates.buyer_payment}.`,
      action: "Confirm the own contribution was paid before the drawdown",
    });
  }

  const uploaded = c.documents.map((d) => d.filename.toLowerCase());
  const missing = c.expected_documents.filter((key) => !uploaded.some((name) => name.includes(key)));
  if (missing.length > 0) {
    findings.push({
      severity: "material",
      title: `${missing.length} required ${missing.length === 1 ? "document" : "documents"} missing`,
      detail: `Missing: ${missing.map(documentName).join(", ")}.`,
      action: "Request the missing documents from the client",
    });
  }

  const unclassified = c.documents.filter((d) => d.label === "jine");
  if (unclassified.length > 0) {
    findings.push({
      severity: "material",
      title: `${unclassified.length} unclassified ${unclassified.length === 1 ? "document" : "documents"}`,
      detail: `Not recognised as a known type: ${unclassified.map((d) => d.filename).join(", ")}.`,
      action: "Classify the document manually",
    });
  }

  if (c.documents.length > 0 && c.principal === null) {
    findings.push({
      severity: "material",
      title: "Loan terms not extracted",
      detail: "Documents are uploaded but no principal, term or dates were extracted.",
      action: "Check the loan agreement and enter the terms",
    });
  }

  if (c.months && c.schedule_rows > 0 && c.schedule_rows < c.months) {
    findings.push({
      severity: "material",
      title: "Repayment schedule incomplete",
      detail: `${c.schedule_rows} of ${c.months} instalments are in the schedule.`,
      action: "Compare the schedule with the loan agreement",
    });
  }

  return findings;
}

// The cases table does not track the lifecycle yet and leaves every case "open",
// so an open case that already has documents is placed by how far intake got.
export function statusOf(c: QueueCase): CaseStatus {
  if (c.status !== "open" || c.documents.length === 0) return c.status;
  return c.principal === null ? "intake_in_progress" : "awaiting_decision";
}

const tierByStatus: Record<CaseStatus, Tier> = {
  awaiting_decision: "decision",
  open: "waiting",
  awaiting_clarification: "waiting",
  intake_in_progress: "processing",
  evaluating: "processing",
  approved: "processing",
  completed: "done",
};

const count = (c: TriagedCase, severity: Severity) => c.findings.filter((f) => f.severity === severity).length;

/** Most acute first: tier, then blocking and material findings, then exposure, then the oldest case. */
export function compareCases(a: TriagedCase, b: TriagedCase): number {
  return (
    tiers.indexOf(a.tier) - tiers.indexOf(b.tier) ||
    count(b, "blocking") - count(a, "blocking") ||
    count(b, "material") - count(a, "material") ||
    (b.principal ?? -1) - (a.principal ?? -1) ||
    a.created_at.localeCompare(b.created_at)
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
