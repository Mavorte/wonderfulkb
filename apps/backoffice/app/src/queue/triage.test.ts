import { test } from "node:test";
import assert from "node:assert/strict";
import triage, { findIssues, statusOf, type QueueCase } from "./triage.ts";

const evaluation = {
  evaluation_id: "ev1",
  status: "completed",
  verdict: "needs_correction",
  summary: null,
  started_at: "2026-10-19T19:00:00Z",
  finished_at: "2026-10-19T19:02:00Z",
  issues: [],
};

const base: QueueCase = {
  case_id: "C1",
  case_found: true,
  client_id: "client-1",
  status: "open",
  created_at: "2026-10-01T00:00:00Z",
  client: { name: "Firma s.r.o.", ico: "12345678", kyc_status: "ok" },
  evaluation,
};

const issue = (rule_id: string, status: string) => ({ rule_id, status, expected: null, found: `${rule_id} ${status}`, reasoning: "" });

test("an open case is placed by its latest evaluator run", () => {
  assert.equal(statusOf(base), "awaiting_decision");
  assert.equal(statusOf({ ...base, evaluation: { ...evaluation, status: "running" } }), "evaluating");
  assert.equal(statusOf({ ...base, evaluation: { ...evaluation, status: "failed" } }), "awaiting_decision");
  assert.equal(statusOf({ ...base, status: "approved" }), "approved");
});

test("evaluator conflicts block, missing items are material, blocking findings come first", () => {
  const findings = findIssues({
    ...base,
    evaluation: { ...evaluation, issues: [issue("invoice_contents", "missing"), issue("recipient_matches_client", "conflict")] },
  });
  assert.deepEqual(
    findings.map((f) => [f.severity, f.title, f.detail]),
    [
      ["blocking", "Recipient matches client record: conflict", "recipient_matches_client conflict"],
      ["material", "Invoice: missing", "invoice_contents missing"],
    ],
  );
});

test("a failed run is a material finding, a missing client or KYC is blocking", () => {
  assert.deepEqual(
    findIssues({ ...base, client: null, evaluation: { ...evaluation, status: "failed" } }).map((f) => [f.severity, f.title]),
    [
      ["blocking", "Client not in registry"],
      ["material", "Checks did not finish"],
    ],
  );
  assert.equal(findIssues({ ...base, client: { ...base.client!, kyc_status: null } })[0].title, "KYC not on file");
  assert.equal(findIssues({ ...base, case_found: false, client: null, client_id: null })[0].title, "Case not in the case registry");
});

test("the queue lists decisions, waiting, processing, then completed cases", () => {
  const queue = triage([
    { ...base, case_id: "done", status: "completed", client: null },
    { ...base, case_id: "processing", evaluation: { ...evaluation, status: "running" } },
    { ...base, case_id: "clarification", status: "awaiting_clarification" },
    { ...base, case_id: "decision" },
  ]);
  assert.deepEqual(
    queue.map((c) => [c.case_id, c.tier]),
    [
      ["decision", "decision"],
      ["clarification", "waiting"],
      ["processing", "processing"],
      ["done", "done"],
    ],
  );
});

test("within a tier, more blockers come first, then more material findings, then the longest-waiting run", () => {
  const queue = triage([
    { ...base, case_id: "clean-old", evaluation: { ...evaluation, started_at: "2026-10-18T00:00:00Z" } },
    { ...base, case_id: "material", evaluation: { ...evaluation, issues: [issue("invoice_contents", "missing")] } },
    { ...base, case_id: "blocking", client: null },
    { ...base, case_id: "clean-new" },
  ]);
  assert.deepEqual(
    queue.map((c) => c.case_id),
    ["blocking", "material", "clean-old", "clean-new"],
  );
});
