import { test } from "node:test";
import assert from "node:assert/strict";
import triage, { findIssues, statusOf, type QueueCase } from "./triage.ts";

const base: QueueCase = {
  case_id: "C1",
  client_id: "client-1",
  status: "awaiting_decision",
  created_at: "2026-10-01T00:00:00Z",
  client: { name: "Firma s.r.o.", ico: "12345678", kyc_status: "ok", kyc_checked_at: "2026-10-01" },
  principal: 1_000_000,
  months: 12,
  schedule_rows: 12,
  disbursement: "supplier_direct",
  dates: { signing: "2026-10-02", payment: "2026-10-03" },
  expected_documents: ["uver", "faktura"],
  documents: [
    { filename: "00_uver.pdf", received_at: "2026-10-02T00:00:00Z" },
    { filename: "01_faktura.pdf", received_at: "2026-10-02T00:00:00Z" },
  ],
};

test("a complete, consistent case awaiting decision has no findings", () => {
  const [c] = triage([base]);
  assert.deepEqual(c.findings, []);
  assert.equal(c.tier, "decision");
});

test("paying the supplier before signing is blocking", () => {
  const findings = findIssues({ ...base, dates: { signing: "2026-10-05", payment: "2026-10-03" } });
  assert.deepEqual(
    findings.map((f) => [f.severity, f.title]),
    [["blocking", "Paid out before signing"]],
  );
});

test("a reimbursed purchase may predate signing", () => {
  const findings = findIssues({
    ...base,
    disbursement: "borrower_reimbursement",
    dates: { signing: "2026-10-05", payment: "2026-10-03" },
  });
  assert.deepEqual(findings, []);
});

test("missing documents, unclassified documents and a short schedule are material", () => {
  const findings = findIssues({
    ...base,
    schedule_rows: 4,
    documents: [{ filename: "00_uver.pdf", received_at: "2026-10-02T00:00:00Z", label: "jine" }],
  });
  assert.deepEqual(
    findings.map((f) => [f.severity, f.title]),
    [
      ["material", "1 required document missing"],
      ["material", "1 unclassified document"],
      ["material", "Repayment schedule incomplete"],
    ],
  );
});

test("an open case with documents is placed by how far intake got", () => {
  assert.equal(statusOf({ ...base, status: "open", documents: [] }), "open");
  assert.equal(statusOf({ ...base, status: "open", principal: null }), "intake_in_progress");
  assert.equal(statusOf({ ...base, status: "open" }), "awaiting_decision");
  assert.equal(statusOf({ ...base, status: "evaluating" }), "evaluating");
});

test("the queue lists decisions, waiting, processing, then completed cases", () => {
  const queue = triage([
    { ...base, case_id: "done", status: "completed", client: null },
    { ...base, case_id: "processing", status: "evaluating" },
    { ...base, case_id: "approved", status: "approved" },
    { ...base, case_id: "clarification", status: "awaiting_clarification" },
    { ...base, case_id: "no-documents", status: "open", client: null, documents: [] },
    { ...base, case_id: "decision" },
  ]);
  assert.deepEqual(
    queue.map((c) => [c.case_id, c.tier]),
    [
      ["decision", "decision"],
      ["no-documents", "waiting"],
      ["clarification", "waiting"],
      ["processing", "processing"],
      ["approved", "processing"],
      ["done", "done"],
    ],
  );
});

test("within a tier, more blockers come first, then the larger exposure", () => {
  const queue = triage([
    { ...base, case_id: "clean", principal: 5_000 },
    { ...base, case_id: "small", client: null, principal: 100 },
    { ...base, case_id: "large", client: null, principal: 900 },
    { ...base, case_id: "two-blockers", client: null, principal: 1, dates: { signing: "2026-10-05", payment: "2026-10-03" } },
  ]);
  assert.deepEqual(
    queue.map((c) => c.case_id),
    ["two-blockers", "large", "small", "clean"],
  );
});
